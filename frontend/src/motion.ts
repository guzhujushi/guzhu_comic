// 全局动效的两个入口：主题圆形揭示、封面 -> 阅读器的共享元素转场。
//
// View Transitions 要有 Chromium 111+（WebView2 常年自动更新，够用）。没有、
// 或者用户开了「减弱动效」，就原样落值 —— 功能一个都不能少，只是没有过渡。
//
// 两个入口都留了兜底：startViewTransition 的回调是浏览器在下一个渲染机会才调的，
// 万一它压根不调（文档不可见、转场被跳过之类），到点自己把活干了 ——
// 主题切了就是切了、章节该跳就得跳，宁可没有过渡，不能让一次点击白费。
const COVER_NAME = 'comic-cover'

/** 主题圆揭示的时长：style.css 里 :root[data-vt="reveal"] 那条也写了 460ms，改动要成对 */
const REVEAL_MS = 460
/** 兜底：这么久还没轮到回调，就别等了 */
const GUARD_MS = 700
/** 转场没正常收尾时的兜底清理延时 */
const SWEEP_MS = 3000

interface ViewTransition {
  ready: Promise<void>
  finished: Promise<void>
}

type VtDocument = Document & {
  startViewTransition?: (cb: () => void | Promise<void>) => ViewTransition
}

/** 用户要求少动：别做过渡，直接落值 */
export function calmMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function canTransition(): boolean {
  return !calmMotion() && typeof (document as VtDocument).startViewTransition === 'function'
}

/** 揭示的起点：给的是点事件就用指针位置，给的是元素就用它的中心 */
function originPoint(origin: HTMLElement | MouseEvent | null): { x: number; y: number } {
  if (origin instanceof MouseEvent) return { x: origin.clientX, y: origin.clientY }
  const box = origin?.getBoundingClientRect()
  if (!box) return { x: window.innerWidth / 2, y: window.innerHeight / 2 }
  return { x: box.left + box.width / 2, y: box.top + box.height / 2 }
}

/**
 * 主题切换：从点击处摊开一个圆，把新配色揭出来。
 *
 * 半径取到离点击点最远的那个角，所以圆一定盖满整屏。动画挂在
 * ::view-transition-new(root) 的 clip-path 上 —— 这是全项目唯一不守「只动
 * transform / opacity」的动画，圆揭示本身就是这个做法，没有别的替代。
 *
 * 挂 data-vt="reveal" 是让样式表把根快照那份默认的淡入淡出按掉（见 style.css）：
 * 留着它，新配色会先整屏淡上来，圆还没扫到的地方就穿帮了。
 *
 * 返回的 Promise 在配色真的换上去之后 resolve —— 回调不是同步跑的，
 * 调用方别把后续动作写在 setTheme 的下一行（比如刷按钮上的图标和文字）。
 */
export function themedReveal(origin: HTMLElement | MouseEvent | null, apply: () => void): Promise<void> {
  if (!canTransition()) {
    apply()
    return Promise.resolve()
  }
  const doc = document as VtDocument
  const { x, y } = originPoint(origin)
  const reach = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
  const root = document.documentElement
  let settled = false
  let resolveApplied!: () => void
  const applied = new Promise<void>((resolve) => { resolveApplied = resolve })
  const release = (): void => {
    if (settled) return
    settled = true
    delete root.dataset.vt
  }
  const applyOnce = (viaGuard: boolean): void => {
    if (settled) return
    apply()
    if (viaGuard) release()      // 没真转场，扫圆的 CSS 门控也就没必要留着
    resolveApplied()
  }
  root.dataset.vt = 'reveal'
  const guard = window.setTimeout(() => applyOnce(true), GUARD_MS)
  try {
    const vt = doc.startViewTransition!(() => {
      window.clearTimeout(guard)
      applyOnce(false)
    })
    void vt.ready.then(() =>
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${reach}px at ${x}px ${y}px)`] },
        {
          duration: REVEAL_MS,
          easing: 'cubic-bezier(.22, .61, .36, 1)',
          pseudoElement: '::view-transition-new(root)',
        } as KeyframeAnimationOptions,
      ),
    )
    const end = (): void => { window.clearTimeout(guard); release() }
    vt.finished.then(end, end)
  } catch (err) {
    window.clearTimeout(guard)
    applyOnce(true)
    console.error(err)
  }
  return applied
}

/**
 * 封面 -> 阅读器：让封面那个矩形「长」成整屏阅读器。
 *
 * 两边都挂 view-transition-name 才能配成一组：详情页封面在转场前挂、新的 .reader
 * 在更新回调里挂。阅读器那份必须在回调 resolve 之前挂上 —— 新快照是回调结束后才拍的，
 * 挂晚了这一趟就退化成普通淡入淡出。
 *
 * 转场结束要两份都摘掉：名字常驻的话，主题圆揭示时阅读器会自己成一个组，
 * 那个组不归 root 的 clip-path 管，就会整块先跳色。
 *
 * 路由切页是同步的，所以回调里等一次 hashchange 就够（router 的监听注册得比我们早，
 * 它先跑完、DOM 已经是阅读器了）；万一 hash 没变、事件不来，还有 1.5s 兜底。
 */
export function morphToReader(from: HTMLElement | null, hash: string): void {
  if (!from || !canTransition() || window.location.hash === hash) {
    window.location.hash = hash
    return
  }
  const doc = document as VtDocument
  let navigated = false
  let guard = 0
  const clean = (): void => {
    window.clearTimeout(guard)
    from.style.removeProperty('view-transition-name')
    document.querySelector<HTMLElement>('.reader')?.style.removeProperty('view-transition-name')
  }
  const go = (): void => {
    if (navigated) return
    navigated = true
    window.location.hash = hash
  }
  from.style.setProperty('view-transition-name', COVER_NAME)
  // 真转场会自己收尾（下面 vt.finished 那条）；这两个是回调没被调时的手刹和扫尾
  guard = window.setTimeout(go, GUARD_MS)
  window.setTimeout(clean, SWEEP_MS)
  try {
    const vt = doc.startViewTransition!(
      () =>
        new Promise<void>((resolve) => {
          const arrive = (): void => {
            document.querySelector<HTMLElement>('.reader')?.style.setProperty('view-transition-name', COVER_NAME)
            resolve()
          }
          const timer = window.setTimeout(arrive, 1500)
          window.addEventListener('hashchange', () => { window.clearTimeout(timer); arrive() }, { once: true })
          go()
        }),
    )
    vt.finished.then(clean, clean)
  } catch (err) {
    clean()
    console.error(err)
    go()
  }
}
