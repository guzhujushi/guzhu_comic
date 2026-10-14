import { createIcon, icons } from './icons.js'
import type { AlbumSummary } from '../types.js'

export class AlbumCard extends HTMLElement {
  constructor() {
    super()
    this.innerHTML = `
      <img alt="" />
      <p></p>
      <span class="album-sub" hidden></span>
    `
  }

  setData(data: AlbumSummary) {
    const img = this.querySelector('img')!
    const p = this.querySelector('p')!
    img.src = data.cover_url ?? 'placeholder.png'
    img.alt = data.title
    p.textContent = data.title
    const sub = this.querySelector<HTMLElement>('.album-sub')!
    sub.textContent = data.subtitle ?? ''
    sub.hidden = !data.subtitle
    this.paintFav(data.favorited === true)
  }

  /**
   * 「已收藏」角标：只有真收藏才挂这个元素 —— 没收藏的卡片**什么都不加**（不留空位、
   * 也不给灰标）。收藏页整页都是收藏、卡片角上已经有删除按钮，那边不传 favorited。
   */
  private paintFav(on: boolean): void {
    this.querySelector('.album-fav')?.remove()
    if (!on) return
    const badge = document.createElement('span')
    badge.className = 'album-fav'
    badge.title = '已收藏'
    badge.appendChild(createIcon(icons.heartOn, { size: 12, stroke: 2.2 }))
    const text = document.createElement('span')
    text.textContent = '已收藏'
    badge.appendChild(text)
    this.appendChild(badge)
  }
}

customElements.define('album-card', AlbumCard)