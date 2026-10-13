import { AlbumCard } from './album.js'
import { renderEmpty } from './states.js'
import type { EmptyOptions } from './states.js'
import type { AlbumSummary } from '../types.js'

export function renderAlbumList(
  albums: AlbumSummary[],
  container: HTMLElement,
  empty?: EmptyOptions,
): void {
  container.innerHTML = ''
  if (albums.length === 0) {
    renderEmpty(container, empty ?? { title: '这里什么都没有，换个条件试试' })
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