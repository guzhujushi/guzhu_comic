// 首页顶部的弧形轮播：三张横向大卡片，中间那张正对，两侧往后转
import type { AlbumSummary } from '../types.js'

export interface HeroHandle {
  destroy(): void
}

const ROTATE_MS = 5200

function calmMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** 还没拿到数据时先摆三块，位置和真卡片一样，免得页面塌一下再跳 */
export function renderHeroSkeleton(container: HTMLElement): void {
  container.innerHTML = `
    <div class="hero-skeleton">
      <div class="skeleton hs-side l"></div>
      <div class="skeleton hs-side r"></div>
      <div class="skeleton hs-main"></div>
    </div>
  `
}

/**
 * 会自己转的小轮播：点两侧的卡片把它转到中间，点中间那张才进详情。
 * 重新渲染前一定要 destroy，不然定时器会越积越多。
 */
export function renderHero(
  container: HTMLElement,
  items: AlbumSummary[],
  onOpen: (id: string) => void,
): HeroHandle {
  container.innerHTML = ''
  if (items.length === 0) return { destroy: () => {} }

  const stage = document.createElement('div')
  stage.className = 'hero-stage'
  container.appendChild(stage)

  let shift = 0
  let timer = 0

  const cards = items.map((item, index) => {
    const card = document.createElement('button')
    card.type = 'button'
    card.className = 'hero-card'

    const img = document.createElement('img')
    img.src = item.cover_url ?? 'placeholder.png'
    img.alt = item.title

    const title = document.createElement('span')
    title.className = 'hero-title'
    title.textContent = item.title

    card.append(img, title)
    card.addEventListener('click', () => {
      if (card.dataset.pos === 'center') onOpen(item.id)
      else {
        shift = index
        layout()
        start()
      }
    })
    stage.appendChild(card)
    return card
  })

  /** center 正对、left / right 往后转；转一次就整组重排一回 */
  function layout(): void {
    const total = cards.length
    cards.forEach((card, index) => {
      const delta = (index - shift + total) % total
      const pos = delta === 0 ? 'center' : delta * 2 <= total ? 'right' : 'left'
      card.dataset.pos = pos
      const front = pos === 'center'
      card.tabIndex = front ? 0 : -1
      const label = front ? items[index].title + '，点开详情' : items[index].title
      card.setAttribute('aria-label', label)
    })
  }

  function start(): void {
    stop()
    if (cards.length < 2 || calmMotion()) return
    timer = window.setInterval(() => {
      shift = (shift + 1) % cards.length
      layout()
    }, ROTATE_MS)
  }

  function stop(): void {
    if (timer) window.clearInterval(timer)
    timer = 0
  }

  // 鼠标停在卡片上就不转，不然点不准
  const onEnter = () => stop()
  const onLeave = () => start()
  const onVisibility = () => {
    if (document.hidden) stop()
    else start()
  }
  stage.addEventListener('mouseenter', onEnter)
  stage.addEventListener('mouseleave', onLeave)
  document.addEventListener('visibilitychange', onVisibility)

  layout()
  start()

  return {
    destroy() {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    },
  }
}