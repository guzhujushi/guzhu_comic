// 品牌字标（「孤竹」那套描边）的**取用口**。
//
// 几何与笔顺的唯一出处是 index.html 里那枚闪屏 SVG —— 全项目就那一份路径数据。
// 闪屏揭幕时整层会被 remove()，之后再 querySelector 就找不到了，所以 main.ts 必须在
// bootSplash() 之后、揭幕之前叫一次 rememberBrandMark()，把路径抄进内存。
// 空状态、加载态这些地方要用字标，就从这里取，不必把路径抄第二遍（改一处漏一处）。

interface Mark {
  viewBox: string
  paths: string[]
}

const SVG_NS = 'http://www.w3.org/2000/svg'

let memo: Mark | null = null

/** 把闪屏里那几笔抄下来；只认第一次，重复调用无副作用 */
export function rememberBrandMark(): void {
  if (memo) return
  const svg = document.querySelector<SVGSVGElement>('#splash-mark')
  if (!svg) return
  const box = svg.getAttribute('viewBox')
  const paths = Array.from(svg.querySelectorAll('path'))
    .map((path) => path.getAttribute('d') ?? '')
    .filter(Boolean)
  if (box && paths.length) memo = { viewBox: box, paths }
}

/** 抄到了没有（老 index.html 没有闪屏 SVG 时是 false，调用方得自己兜底） */
export function hasBrandMark(): boolean {
  return memo !== null
}

/**
 * 造一枚字标：描边走 currentColor（深浅两套主题同一份代码），宽度给定、高度按 viewBox 的
 * 宽高比算，免得拉伸。抄不到路径就返回 null。
 */
export function brandMark(width: number, className = 'brand-mark-svg'): SVGSVGElement | null {
  if (!memo) return null
  const [vx, vy, vw, vh] = memo.viewBox.split(/[\s,]+/).map(Number)
  if (![vx, vy, vw, vh].every(Number.isFinite) || vw <= 0 || vh <= 0) return null

  const svg = document.createElementNS(SVG_NS, 'svg')
  svg.setAttribute('viewBox', memo.viewBox)
  svg.setAttribute('width', String(width))
  svg.setAttribute('height', String(Math.round((width * vh) / vw)))
  svg.setAttribute('aria-hidden', 'true')
  svg.setAttribute('class', className)
  for (const d of memo.paths) {
    const path = document.createElementNS(SVG_NS, 'path')
    path.setAttribute('d', d)
    path.setAttribute('fill', 'none')
    path.setAttribute('stroke', 'currentColor')
    // 25 是闪屏那套笔宽，跟着 viewBox 一起缩放 —— 字标看着才跟开场那枚是同一支笔
    path.setAttribute('stroke-width', '25')
    path.setAttribute('stroke-linecap', 'round')
    path.setAttribute('stroke-linejoin', 'round')
    svg.appendChild(path)
  }
  return svg
}
