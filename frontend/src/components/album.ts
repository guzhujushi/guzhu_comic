export interface AlbumSummary {
  id: string
  title: string
  cover_url?: string
}

export class AlbumCard extends HTMLElement {
  constructor() {
    super()
    this.innerHTML = `
      <img alt="" />
      <p></p>
    `
  }

  setData(data: AlbumSummary) {
    const img = this.querySelector('img')!
    const p = this.querySelector('p')!
    img.src = data.cover_url ?? 'placeholder.png'
    img.alt = data.title
    p.textContent = data.title
  }
}

customElements.define('album-card', AlbumCard)