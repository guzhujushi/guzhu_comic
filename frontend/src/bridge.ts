// P0：本地 HTTP 桥（`POST /api`；协议与理由见 backend/bridge.py 开头）。
//
// 壳（桌面 `main.py` / 安卓 `android_boot.py`）把这次开窗的 token 拼在页面地址上（`?t=...`），
// 这个模块一看到它就**顶替掉 pywebview 的 js_api**：页面里那几十处
// `window.pywebview.api.xxx(...)` 一行都不用改，底下走的是 fetch。
//
// 谁在什么时候装：
//   * 打包态桌面 / 安卓：地址上有 `?t=` → 装上 → 页面完全不碰 pywebview（桌面那边也就不再挂
//     `js_api`，"注两遍 / 把在飞调用的回调清掉"那类坑整类消失）；
//   * 源码态 dev（vite 喂页面）：没有 `?t=` → **什么都不装**，原生 js_api 照旧；
//   * 用户自己拿浏览器打了 `127.0.0.1:47753`（没带 token）：两边都没有 → 页面走各页自己那句
//     "桥没连上"，提示里带着"用带 ?t= 的地址打开"。
//
// 方法引用必须**稳定**：`webstatus.ts` 的启动闸门是靠"同一个方法的引用变没变"判断桥有没有被
// 重新注入的。所以下面按名字缓存函数 —— 每次现造一个新函数的话，那个闸门会一直等下去。
//
// 一条纪律：**别把这个 api 对象上的名字当数据**。它是代理，任何名字都返回一个函数
// （`await api` 那种则被下面的 then/catch/finally 挡掉）。要判断"桥在不在"看 `bridgeMode`。

const TOKEN_KEY = 'guzhu:bridge:token'
const RPC_PATH = '/api'
const TOKEN_HEADER = 'X-Guzhu-Token'

/** 这次开窗的通行证：地址上的 `?t=` 优先，其次上次存下的那份（刷新页面不掉） */
function pickToken(): string | null {
  const fromUrl = new URLSearchParams(location.search).get('t')
  if (fromUrl) {
    // 存一份：用户把地址栏里的 ?t= 删了再回车，或从书签进来，也还能用
    try { sessionStorage.setItem(TOKEN_KEY, fromUrl) } catch { /* 存储被禁：URL 那份够用 */ }
    return fromUrl
  }
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}

async function call(token: string, name: string, args: unknown[]): Promise<unknown> {
  let res: Response
  try {
    res = await fetch(RPC_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', [TOKEN_HEADER]: token },
      body: JSON.stringify({ name, args }),
    })
  } catch (err) {
    // 服务没了 / 页面是被别的程序打开的：明确说一句，别让调用方以为"这个方法不存在"
    throw new Error(`本地服务没应答：${err instanceof Error ? err.message : String(err)}`)
  }
  const text = await res.text()
  let data: { __result__?: unknown; __error__?: string }
  try {
    data = JSON.parse(text) as { __result__?: unknown; __error__?: string }
  } catch {
    throw new Error(`本地服务回了非 JSON（HTTP ${res.status}）：${text.slice(0, 200)}`)
  }
  // 后端的约定：方法里抛什么就 __error__ 回什么（见 backend/bridge.py）—— 原样抛给调用方，
  // 各页 catch 之后写进界面的那句提示才和以前（走 js_api 时）一致
  if (typeof data.__error__ === 'string') throw new Error(data.__error__)
  if (!res.ok) throw new Error(`本地服务回了 HTTP ${res.status}`)
  return data.__result__
}

function makeApi(token: string): PyApi {
  const cache = new Map<string, (...args: unknown[]) => Promise<unknown>>()
  return new Proxy({} as PyApi, {
    get(_target, name) {
      if (typeof name !== 'string') return undefined
      // then / catch / finally **必须回 undefined**：代理对任何属性都回函数的话，api 自己就成了
      // thenable —— `await api` 会去调 then(resolve, reject) 而永不 settle，整个启动挂在
      // await 上（假桥踩过这个坑，见 tmp/_pc_bridge.js）
      if (name === 'then' || name === 'catch' || name === 'finally') return undefined
      let fn = cache.get(name)
      if (!fn) {
        fn = (...args: unknown[]) => call(token, name, args)
        cache.set(name, fn)
      }
      return fn
    },
  })
}

const token = pickToken()
const nativeApi = window.pywebview?.api

/** 这次开窗走的哪条桥：`http`（本地服务）/ `native`（pywebview js_api）/ `none`。排障看它 */
export const bridgeMode: 'http' | 'native' | 'none' =
  token && !nativeApi ? 'http' : nativeApi ? 'native' : 'none'

if (bridgeMode === 'http') {
  window.pywebview = { api: makeApi(token as string) }
  console.log(`[bridge] 本地 HTTP 桥已就位（POST ${RPC_PATH}）`)
} else if (bridgeMode === 'none') {
  console.warn('[bridge] 地址上没有 ?t=，也没有原生桥：用启动日志里那条带 ?t= 的地址打开')
}