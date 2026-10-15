// 列表和详情页共用的几种状态：空空如也、加载中、出错
import { brandMark } from './brand.js'

export interface EmptyOptions {
  icon?: string
  avatar?: boolean   // 要插图（品牌字标），别给 emoji
  title: string
  hint?: string
  actionLabel?: string
  onAction?: () => void
}

/**
 * 空状态：插图 + 标题 + 说明 + 可选按钮，文字一律走 textContent，免得拼串被转义坑到。
 *
 * 插图三档（2026-10-15）：给了 icon 就用那枚 emoji（⚠️ / 🔍 这类有含义的照样留着）；
 * 否则用品牌「孤竹」字标（`avatar: true` 与默认都是它）；字标取不到（老 index.html
 * 没有闪屏 SVG）才退回那张方头像 / 📭 —— 视觉上始终有东西，不会留白。
 */
export function renderEmpty(container: HTMLElement, opts: EmptyOptions): void {
  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-art"></div>
      <p class="empty-title"></p>
      <p class="empty-sub"></p>
      <button type="button" class="empty-action"></button>
    </div>
  `
  const art = container.querySelector<HTMLElement>('.empty-art')!
  if (opts.icon) {
    const box = document.createElement('div')
    box.className = 'empty-icon'
    box.textContent = opts.icon
    art.appendChild(box)
  } else {
    const mark = brandMark(172)
    if (mark) {
      mark.classList.add('empty-mark')
      art.appendChild(mark)
    } else {
      const img = document.createElement('img')
      img.className = 'empty-avatar'
      img.src = '/apple-touch-icon.png'
      img.alt = ''
      art.appendChild(img)
    }
  }
  container.querySelector('.empty-title')!.textContent = opts.title

  const sub = container.querySelector<HTMLElement>('.empty-sub')!
  if (opts.hint) sub.textContent = opts.hint
  else sub.remove()

  const btn = container.querySelector<HTMLButtonElement>('.empty-action')!
  if (opts.actionLabel) {
    btn.textContent = opts.actionLabel
    btn.addEventListener('click', () => opts.onAction?.())
  } else {
    btn.remove()
  }
}

/** 出错就套空状态的外壳，给不给重试按钮都行 */
export function renderError(container: HTMLElement, message: string, retry?: () => void): void {
  renderEmpty(container, {
    icon: '⚠️',
    title: '加载失败了',
    // pywebview 抛回来的错误串前面总带个 "Error: "，摆到界面上太噪
    hint: message.replace(/^Error:\s*/, ''),
    actionLabel: retry ? '重试' : undefined,
    onAction: retry,
  })
}

/** 卡片列表的占位：用假的卡片骨架顶住布局，别让页面先塌一下再跳 */
/** 评论流的占位：图源第一次响应能等十几秒，这会儿不能什么都不铺，不然看着像"论坛是空的" */
export function renderCommentSkeleton(container: HTMLElement, count = 5): HTMLElement[] {
  const made: HTMLElement[] = []
  for (let i = 0; i < count; i++) {
    const el = document.createElement('article')
    el.className = 'comment comment-skeleton'
    el.innerHTML = `
      <div class="skeleton sk-line short"></div>
      <div class="skeleton sk-line"></div>
      <div class="skeleton sk-line"></div>
    `
    container.appendChild(el)
    made.push(el)
  }
  return made
}

export function renderAlbumSkeleton(container: HTMLElement, count = 10): void {
  container.innerHTML = Array.from({ length: count }, () => `
    <div class="album-skeleton">
      <div class="skeleton sk-cover"></div>
      <div class="skeleton sk-line"></div>
      <div class="skeleton sk-line short"></div>
    </div>
  `).join('')
}