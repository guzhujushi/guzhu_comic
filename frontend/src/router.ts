import { renderError } from './components/states.js'

type RouteHandler = (params: Record<string, string>) => HTMLElement | void

interface Route {
  path: string
  handler: RouteHandler
}

const routes: Route[] = []

/** 当前页面注册的收尾函数（存进度、解绑监听之类），路由切走前统一执行 */
const cleanups: (() => void)[] = []

export function onUnmount(fn: () => void): void {
  cleanups.push(fn)
}

function runCleanups(): void {
  for (const fn of cleanups.splice(0)) {
    try {
      fn()
    } catch (err) {
      console.error(err)
    }
  }
}

export function registerRoute(path: string, handler: RouteHandler) {
  routes.push({ path, handler })
}

export function navigate(path: string) {
  window.location.hash = path
}

function parseHash(): { path: string; params: Record<string, string> } {
  const raw = window.location.hash.slice(1) || '/'  // 去掉开头的 #
  const [path, queryString = ''] = raw.split('?')

  const params: Record<string, string> = {}
  if (queryString) {
    for (const [k, v] of new URLSearchParams(queryString)) {
      params[k] = v
    }
  }

  return { path, params }
}

// 列表页"回到原处"的记忆：地址（含参数）→ 离开时看到哪儿了。
// 只活在这一次会话里 —— 刷新 / 重开窗口从头开始，够用，也别往磁盘上落东西。
const scrollMemo = new Map<string, number>()
const MEMO_MAX = 60
/** 屏幕上这一页是哪条地址 —— 滚动位置记在它名下，而不是"地址栏里现在这条" */
let currentKey = ''

/** 位置随手记一条：键 = 渲染时那条地址，值取整（免得浮点在那儿抖） */
function rememberScroll(key: string, y: number): void {
  scrollMemo.set(key, Math.round(y))
  while (scrollMemo.size > MEMO_MAX) {
    const oldest = scrollMemo.keys().next().value
    if (oldest === undefined) break
    scrollMemo.delete(oldest)
  }
}

/**
 * 只有"从历史里退回来 / 退到前面"才回到原处，点导航栏去别的页还是从头看。
 *
 * 光听 popstate 认不出来：Chrome 在 hash 变化时**也会**甩一个 popstate（跟 hashchange 前后脚到），
 * 于是"点导航进新页面"也被当成退回来，位置就留在上一页那儿不动（实测 500 没回顶）。
 * 所以自己给每条历史记录盖一个递增序号：序号跟当前这条不一样 = 历史穿梭（前进 / 后退），
 * 一样（或没盖过章）= 页面自己写 hash 推出来的新条目。
 */
let traversed = false
let historySeq = 0

/** 读当前这条历史记录的章；null = 没盖过（我们接手前就有的条目，或者刚推出来的新条目） */
function readSeq(): number | null {
  const state = window.history.state as { __seq?: number } | null
  return state && typeof state.__seq === 'number' ? state.__seq : null
}

/** 给当前这条记录盖 / 保一枚章（穿梭回旧条目时旧号原样留着） */
function stampSeq(): void {
  try {
    window.history.replaceState({ __seq: historySeq }, '')
  } catch {
    // 老 WebView 不给动 state：退回"一律当新页面"，宁可从顶部看也别卡在半空
  }
}

/**
 * 只改地址栏、不往历史里堆一条（翻页那种"同一次浏览"的地址更新）。
 * 走这里而不是直接 replaceState：得把这条记录的序号章原样带过去 ——
 * 否则从详情返回时认不出"这是退回来的那条"，页码对了滚动位置也会丢。
 */
export function replaceHash(next: string): void {
  try {
    window.history.replaceState(window.history.state, '', next)
    currentKey = keyOf()   // 地址变了，屏幕上这页就归新地址了（翻页那种）
  } catch {
    // 改不动就拉倒：地址栏不好看而已，页面本身照旧
  }
}

/** 地址（含参数）当键：`#/category?c=doujin` 跟 `#/search?q=a` 各记各的 */
function keyOf(): string {
  const { path, params } = parseHash()
  const query = Object.keys(params).sort().map((k) => `${k}=${params[k]}`).join('&')
  return query ? `${path}?${query}` : path
}

/** 地址里的页码：认不出、越界都当第 1 页（"顺着往下翻"的列表页用得上） */
export function pageParam(params: Record<string, string>, max = 60): number {
  const n = Math.floor(Number(params.page))
  return Number.isFinite(n) && n > 1 ? Math.min(n, max) : 1
}

/**
 * 页面长度是一帧帧长出来的（先骨架、后数据），页面还不够长时 scrollTo 打不到底，
 * 所以给自己几次重试；用户自己一滚（滚轮 / 触摸）就立刻放手，别抢方向盘。
 */
function restoreScroll(target: number): void {
  if (target <= 0) return
  let cancelled = false
  const cancel = () => { cancelled = true }
  window.addEventListener('wheel', cancel, { passive: true })
  window.addEventListener('touchmove', cancel, { passive: true })
  const stop = () => {
    window.removeEventListener('wheel', cancel)
    window.removeEventListener('touchmove', cancel)
  }
  let tries = 0
  const kick = () => {
    if (cancelled) return stop()
    window.scrollTo(0, target)
    tries += 1
    if (Math.abs(window.scrollY - target) <= 1 || tries >= 20) return stop()
    window.setTimeout(kick, 120)
  }
  window.setTimeout(kick, 0)
}

function resolve() {
  const back = traversed           // 这次是"退回来"还是"点出去"，决定要不要还原滚动位置
  traversed = false
  // 要落到的那个地址，**挂载前**就先量好：页面挂载时可能顺手改地址 ——
  // 分类页重算页码那一下会把 `&page=3` 先摘掉、数据回来再补上，等挂载完再读就对不上了，
  // memo 里那条（返回时按旧地址记的）就白记了。
  const targetKey = keyOf()
  // 趁页面还在、位置还没被搅乱，先把"看到哪儿了"记在**刚刚这一页**名下。
  // 这会儿地址栏已经换成新地址了，所以键要用 currentKey，不能现读 location.hash。
  if (currentKey) rememberScroll(currentKey, window.scrollY)
  runCleanups()
  const { path, params } = parseHash()

  const container = document.querySelector<HTMLDivElement>('#app')
  // 页面结构不对（index.html 被改过）时，至少别把异常抛进事件回调里
  if (!container) return

  for (const route of routes) {
    if (route.path !== path) continue
    container.innerHTML = ''
    try {
      const result = route.handler(params)
      if (result) container.appendChild(result)
    } catch (err) {
      // 页面**挂载那一刻**就抛异常的话，container 已经被清空了 —— 不兜这一下就是整窗空白、
      // 连一句提示都没有（各页面自己的 try/catch 管的是它们之后的异步加载，管不到这里）。
      console.error(`页面渲染失败：${path}`, err)
      container.innerHTML = ''
      renderError(container, `这个页面没能打开（${path}）：${String(err)}`, resolve)
    }
    // 阅读器有自己的"回到第 N 页"（见 reader.ts 的进度恢复），这条规则两边都不管它
    if (path !== '/read') {
      if (back) restoreScroll(scrollMemo.get(targetKey) ?? 0)
      // 主动点进新页面就从顶部看起：hash 导航不会自己回顶，不顺这一下就会接着上一页的位置
      else window.scrollTo(0, 0)
    }
    currentKey = keyOf()
    return
  }

  // 没有匹配的路由
  currentKey = ''
  container.textContent = `404: ${path}`
}

export function startRouter() {
  // 浏览器自己也有一套滚动还原：它在 hash 切完之后才动手，会把我们那下 scrollTo 顶掉
  // （点导航进新页面还停在上一页的位置）。关掉它，还原只走上面那份 scrollMemo。
  if ('scrollRestoration' in window.history) window.history.scrollRestoration = 'manual'
  // 每条历史记录发一个号：手写 hash 推出来的新条目盖新号，从历史里穿梭回来的原样带着旧号
  historySeq = readSeq() ?? 0
  stampSeq()
  window.addEventListener('hashchange', () => {
    const seq = readSeq()
    traversed = seq !== null && seq !== historySeq
    historySeq = seq === null ? historySeq + 1 : seq
    stampSeq()
    resolve()
  })

  // 滚动位置随手记（键 = 屏幕上这一页，见 currentKey）。
  // ① 别塞进 requestAnimationFrame 里再读：那一帧可能拖到页面都换完了 —— 位置就记到新页面名下，
  //    返回时找不着（headless 探针里实测被拖了 900ms 都不止）。
  // ② 也别指望这监听一定跑得到：Chrome 的滚动事件是"下一帧派发"，离手太快（程序滚动完立刻跳页）
  //    就赶不上。所以 resolve() 里离开页面前还会再记一次，那次才是保底的。
  window.addEventListener('scroll', () => {
    if (currentKey) rememberScroll(currentKey, window.scrollY)
  }, { passive: true })

  // 没有 hash 就默认跳 /popular（赋值会触发 hashchange -> resolve）；
  // 不再监听 DOMContentLoaded：它和首次 hashchange 会让首页被渲染两遍
  if (window.location.hash) {
    resolve()
  } else {
    window.location.hash = '/popular'
  }
}