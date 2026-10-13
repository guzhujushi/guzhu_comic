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
  }
}

customElements.define('album-card', AlbumCard)