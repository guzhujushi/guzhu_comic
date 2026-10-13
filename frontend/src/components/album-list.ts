import { AlbumCard } from './album.js'
import type { AlbumSummary } from '../types.js'

export function renderAlbumList(albums: AlbumSummary[], container: HTMLElement): void {
  container.innerHTML = ''
  if (albums.length === 0) {
    container.innerHTML = '<p class="empty-hint">这里什么都没有，换个条件试试</p>'
    return
  }
  for (const item of albums) {
    const card = new AlbumCard()
    card.setData(item)
    card.addEventListener('click', () => {
      window.location.hash = `#/album?id=${item.id}`
    })
    container.appendChild(card)
  }
}