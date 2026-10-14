// 开场闪屏：内联在 index.html 里的那一块，这里只管两件事 —— 什么时候揭幕、怎么飞进左上角。
//
// 计时的尺子和内联 CSS 那串描字动画是同一把：performance.now() 的零点就是页面开始加载，
// 而描字是首帧就起跑的。所以"最早揭幕"直接按页面加载算，不用再对一次表。
import { DEFAULT_SETTINGS } from './settings.js'

/** 6 笔合起来的描字时长，跟 index.html 里那串 animation-duration 对得上 */
const DRAW_MS = 1500
/** 字写完再停一下，别让人刚看清就飞走 */
const HOLD_MS = 450
/** 落位那一飞 */
const FLIP_MS = 380
/** 背景淡出 */
const FADE_MS = 120

interface SplashTiming {
  enabled: boolean
  min_ms: number
  max_ms: number
}

let layer: HTMLElement | null = null      // #splash 整层
let mark: SVGSVGElement | null = null     // 正在描的那个字标
let slot: HTMLElement | null = null       // 导航里那个落点
let arrived = false                       // 首页铺完了没
let dismissed = false
let earliest = 0                          // 最早揭幕时刻（从页面开始加载算起的毫秒）
let minTimer = 0
let maxTimer = 0

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * 接管内联闪屏。
 *
 * 先拿默认配置跑着（配置要等桥就绪才拿得到，那会儿闪屏早就在画了），
 * 配置到手再调 splashConfigure() 校正。
 */
export function bootSplash(timing: SplashTiming = DEFAULT_SETTINGS.splash): void {
  const el = document.querySelector<HTMLElement>('#splash')
  const svg = document.querySelector<SVGSVGElement>('#splash-mark')
  if (!el || !svg) return       // 页面里没有闪屏（比如旧 index.html）：什么都不做，回到改版前的样子
  layer = el
  mark = svg
  slot = placeNavMark(svg)
  splashConfigure(timing)
  window.addEventListener('pointerdown', onSkip, true)
  window.addEventListener('keydown', onKey, true)
}

/** 配置到手后校正一遍：关了就当场撤（内联闪屏在那之前就已经在画了），时长按配置重排 */
export function splashConfigure(timing: SplashTiming): void {
  if (!layer || dismissed) return
  if (!timing.enabled) {
    dismiss()
    return
  }
  earliest = Math.max(calm ? 0 : DRAW_MS + HOLD_MS, timing.min_ms)
  window.clearTimeout(minTimer)
  window.clearTimeout(maxTimer)
  const now = performance.now()
  minTimer = window.setTimeout(whenEarliest, Math.max(0, earliest - now))
  maxTimer = window.setTimeout(dismiss, Math.max(0, timing.max_ms - now))
}

/** 首页铺完（成功或首次失败都算）时叫一声：闪屏不用再干等到上限 */
export function splashReady(): void {
  arrived = true
  whenEarliest()
}

function whenEarliest(): void {
  if (!layer || dismissed) return
  if (arrived && performance.now() >= earliest) dismiss()
}

/**
 * 揭幕：背景淡出，字标飞进左上角。
 *
 * 飞的是同一个元素（FLIP：量首末矩形 → transform 反向偏移 → 播 → 交棒静态 DOM），
 * 落位那一下正好盖在导航里那份同尺寸的字标上，所以看不出接缝。
 */
function dismiss(): void {
  if (dismissed || !layer) return
  dismissed = true
  window.clearTimeout(minTimer)
  window.clearTimeout(maxTimer)
  window.removeEventListener('pointerdown', onSkip, true)
  window.removeEventListener('keydown', onKey, true)

  const el = layer
  const svg = mark
  const target = slot
  layer = null
  mark = null
  slot = null

  finishMark(svg)             // 提前跳过的话，把没描完的补上
  el.dataset.out = '1'        // 底色淡出；字标自己还在，接着飞

  const box = svg ? svg.getBoundingClientRect() : null
  const to = target ? target.getBoundingClientRect() : null
  if (!svg || calm || !box || !to || box.width <= 1 || to.width <= 1) {
    if (svg) {
      svg.style.transition = `opacity ${FADE_MS}ms linear`
      svg.style.opacity = '0'
    }
    window.setTimeout(() => reveal(el, target), FADE_MS)
    return
  }

  // transform-origin 得显式写：SVG 元素默认的变换原点不是左上角，不写这一段飞行就是斜的。
  // 用 WAAPI 而不是 transition：省掉"先让样式落一帧"那次强制 reflow。
  svg.style.transformOrigin = 'top left'
  const scale = to.width / box.width
  svg.animate(
    [
      { transform: 'none' },
      { transform: `translate(${to.left - box.left}px, ${to.top - box.top}px) scale(${scale})` },
    ],
    { duration: FLIP_MS, easing: 'cubic-bezier(.22,.61,.36,1)', fill: 'forwards' },
  )
  window.setTimeout(() => reveal(el, target), FLIP_MS + 20)
}

/** 闪屏整层撤掉，导航里那份字标露出来 */
function reveal(el: HTMLElement, target: HTMLElement | null): void {
  el.remove()
  if (target) target.style.visibility = ''
}

/**
 * 把字标克隆一份放进左侧导航的品牌位（先藏着占住位置），返回那个落点。
 *
 * 只从闪屏那份克隆，路径数据就不会两个地方各写一遍再改漏。
 */
function placeNavMark(src: SVGSVGElement): HTMLElement | null {
  const home = document.querySelector<HTMLElement>('.brand-mark')
  if (!home) return null
  const clone = src.cloneNode(true) as SVGSVGElement
  clone.removeAttribute('id')
  clone.removeAttribute('style')
  // 渐变是闪屏那份专用的（导航里用 currentColor 跟主题走），留着就是两个同 id 的元素
  for (const defs of Array.from(clone.querySelectorAll('defs'))) defs.remove()
  clone.classList.add('brand-logo')   // role / aria-label 跟着过来，读屏念得出这是字标
  for (const path of Array.from(clone.querySelectorAll('path'))) {
    path.removeAttribute('style')       // 导航里是静态的：那串描字动画不要
  }
  home.textContent = ''
  home.appendChild(clone)
  home.style.visibility = 'hidden'      // 等字标飞过来再露，免得"两个 GuZhu"同框
  return home
}

/** 跳过时把描字补完：动画停掉，直接停在写完的样子 */
function finishMark(svg: SVGSVGElement | null): void {
  if (!svg) return
  for (const path of Array.from(svg.querySelectorAll('path'))) {
    path.style.animation = 'none'
    path.style.strokeDashoffset = '0'
  }
}

function onSkip(): void {
  dismiss()
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') dismiss()
}
