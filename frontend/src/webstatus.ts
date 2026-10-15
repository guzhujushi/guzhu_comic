// 和 pywebview 的 JS 桥打交道：什么时候算"能用"、怎么调才不会被它自己清掉。

/** 桥"能用"了吗：给了 method 就要求那个方法真的挂上了，不只是 api 对象在 */
function readyApi(method?: keyof PyApi): PyApi | null {
  const api = window.pywebview?.api
  if (!api) return null
  if (method && typeof api[method] !== 'function') return null
  return api
}

/**
 * 「pywebview 启动那几百毫秒，这个文档可能被注入两遍」这件事的来龙去脉。
 *
 * 每一遍注入都是：`js/api.js` 先把 `window.pywebview = {api: {}, _returnValuesCallbacks: {}}`
 * 摆上，`js/finish.js` 再 `_createApi()` 挂方法、派发 `pywebviewready`（2026-10-14 真窗口探针
 * 实测：两次 `inject_pywebview` 间隔 50ms ~ 400ms 不等，偶尔只注一遍）。而 `_createApi()` 里
 * 那句 `_returnValuesCallbacks[funcName] = {}` 是**重建**：第二遍一跑，**正在飞的调用，回调表就没了**。
 * Python 侧算完回头 `evaluate_js` 去调 `_returnValuesCallbacks[func][id]`，那儿已经不是函数
 * （真机报错长这样：`window.pywebview._returnValuesCallbacks.get_settings.9930549249075583
 * is not a function`），JS 这边那个 promise 于是**永远不 settle** —— `await` 直接挂死。实测：
 * 436ms 发出的 get_settings / get_history 撞上第二遍注入，`await loadSettings()` 再没回来、
 * `startRouter()` 没跑到，整个窗口一片空白。
 *
 * 所以两道保险都要：① 启动闸门等最后一次注入**安静下来**再放行（`waitForBridge` 的 quietMs）；
 * ② 启动路径上的**读**调用走 `bridgeCall()`，被清掉能自己重来。
 */

/**
 * 每个方法「最后一次换了一套新函数」的时刻。
 *
 * `_createApi()` 每跑一遍都是 `new Function(...)` **现造**一套函数，所以同一个方法的引用变了，
 * 就是又注入了一遍 —— 这比只听 `pywebviewready` 可靠：事件有可能在我们的监听挂上之前就派发完了
 * （真机上遇到过：桥比我们的脚本先挂好，于是"最近一次注入"无从得知，闸门当场放行、正撞上第二遍）。
 */
const remountAt = new Map<string, number>()
const seenFn = new Map<string, unknown>()

function noteMount(api: PyApi, method: string): number {
  const fn = (api as unknown as Record<string, unknown>)[method]
  if (seenFn.get(method) !== fn) {
    seenFn.set(method, fn)
    remountAt.set(method, Date.now())
  }
  return remountAt.get(method) ?? 0
}

/** 正在飞的桥调用：下一次注入一到，它们的回调就没了 —— 当场判死，别让调用方干等 */
import { bridgeMode } from './bridge'

const inflight = new Set<{ reject: (err: Error) => void }>()

window.addEventListener('pywebviewready', () => {
  // HTTP 垫片那一档（打包态桌面 / 安卓）：注进来的是**空**的原生桥，我们的调用走 `fetch`，
  // 回调压根不在 pywebview 那儿 —— 判死纯属误伤（写调用还得白白丢一次，见 bridge.ts）
  if (bridgeMode !== 'native') return
  const err = new Error('pywebview 又注入了一遍：这次调用的回调被清掉了')
  for (const entry of [...inflight]) entry.reject(err)
  inflight.clear()
})

/**
 * 等桥可用：方法真的挂上（默认 `get_settings`）**并且离最后一次注入过了 quietMs**
 * （这段时间里没有新的 `pywebviewready`、方法也没被换成一整套新的）。
 * 等它静下来再开工，正在飞的调用才不会被下一遍注入清掉（见上面那段）。
 *
 * quietMs 取 800：探针实测那两遍最多差到 400ms 上下，取 400 会漏。多等这一会儿不白花 ——
 * 揭幕那层闪屏本来就要等首页铺完（`splashReady`）才走，用户看不见。
 *
 * **别退回"只判 `window.pywebview?.api` 在不在"**：`js/api.js` 先建的是个**空对象**，
 * `finish.js` 那边才把方法挂上；两步之间 `api` 判真、方法全是 undefined ——
 * 「第一次进首页没有推荐段 / 没有继续阅读」就是这么来的。
 */
export function waitForBridge(
  method: keyof PyApi = 'get_settings', timeoutMs = 5000, quietMs = 800,
): Promise<PyApi> {
  return new Promise((resolve, reject) => {
    const started = Date.now()
    const timer = window.setInterval(() => {
      if (check()) return
      if (Date.now() - started >= timeoutMs) {
        window.clearInterval(timer)
        window.removeEventListener('pywebviewready', check)
        reject(new Error(`pywebview 桥超时：${String(method)} 一直没就绪`))
      }
    }, 100)
    function check(): boolean {
      const api = readyApi(method)
      if (!api) return false
      // 方法被换了一套新的 = 刚又注入了一遍，重新开始计时（见上面 noteMount）
      if (Date.now() - noteMount(api, method) < quietMs) return false
      window.clearInterval(timer)
      window.removeEventListener('pywebviewready', check)
      resolve(api)
      return true
    }
    window.addEventListener('pywebviewready', check)
    check()
  })
}

/** 回调被下一次注入清掉 / 桥一直不回 —— 都算"这次调用白打了"，交给 bridgeCall 重发 */
class BridgeLost extends Error {}
class BridgeTimeout extends Error {}

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => window.setTimeout(resolve, ms))

/** 给一次桥调用加两道保险：注入把回调清掉时当场判死；一直不回给个兜底（正常走不到） */
async function guarded<T>(call: Promise<T>, timeoutMs: number): Promise<T> {
  let rejectLost: (err: Error) => void = () => undefined
  const lost = new Promise<never>((_, reject) => { rejectLost = reject })
  const entry = { reject: rejectLost }
  inflight.add(entry)
  let timer = 0
  try {
    const timeout = new Promise<never>((_, reject) => {
      timer = window.setTimeout(() => reject(new BridgeTimeout(`桥调用超时（${timeoutMs}ms）`)), timeoutMs)
    })
    return await Promise.race([call, lost, timeout])
  } finally {
    window.clearTimeout(timer)
    inflight.delete(entry)
  }
}

/**
 * **读接口**专用：替你把 `window.pywebview.api.xxx(...)` 调稳。
 * 被下一次注入清掉（BridgeLost）就等桥安静下来重发，最多 tries 次；后端真报的错原样抛出去。
 *
 * **写接口别用**：`toggle_favorite` / `save_progress` 这类不幂等，重放等于翻两次；而且写调用
 * 都不在启动路径上 —— 撞上"注入那 1 秒"的概率本来就绑在启动那一刻。
 */
export async function bridgeCall<M extends keyof PyApi>(
  method: M, args: Parameters<PyApi[M]>, tries = 3, timeoutMs = 20000,
): Promise<Awaited<ReturnType<PyApi[M]>>> {
  let last: unknown = null
  for (let attempt = 0; attempt < tries; attempt++) {
    const api = readyApi(method)
    if (!api) {
      last = new Error(`pywebview 桥没就绪：${String(method)}`)
      await sleep(150)
      continue
    }
    const call = api[method] as (...a: unknown[]) => Promise<Awaited<ReturnType<PyApi[M]>>>
    try {
      return await guarded(call.apply(api, args), timeoutMs)
    } catch (err) {
      if (!(err instanceof BridgeLost || err instanceof BridgeTimeout)) throw err
      last = err
      await waitForBridge(method, 3000).catch(() => undefined)   // 等这次注入落定再来
    }
  }
  throw last instanceof Error ? last : new Error(`桥调用失败：${String(method)}`)
}

/**
 * 桥还没注入好时"盯着它"：真就绪了再回来接着干活。
 * 启动那一下偶尔会慢半拍，页面这边别一看到没有 api 就报死错误。
 */
export function waitForApi(tries = 24, gap = 500): Promise<PyApi> {
  const ready = window.pywebview?.api
  if (ready) return Promise.resolve(ready)
  return new Promise((resolve, reject) => {
    let left = tries
    const timer = window.setInterval(() => {
      const api = window.pywebview?.api
      if (api) {
        window.clearInterval(timer)
        resolve(api)
        return
      }
      if (--left <= 0) {
        window.clearInterval(timer)
        reject(new Error('pywebview api 一直没就绪'))
      }
    }, gap)
  })
}
