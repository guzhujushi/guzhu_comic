// pages/favorites.ts
import { AlbumCard } from '../components/album.js'
import { createIcon, icons } from '../components/icons.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import type { FavoriteItem } from '../types.js'

/** 我的收藏：读的是本地 sqlite 表（data/app.db 的 favorite），跟图源账号无关 */
export function favoritesPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'favorites-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">我的收藏</h1>
      <p class="page-sub">存在本机，清缓存也删不掉</p>
    </header>
    <p class="fav-error" hidden></p>
    <div class="album-list"></div>
  `

  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const errorEl = el.querySelector<HTMLParagraphElement>('.fav-error')!
  let items: FavoriteItem[] = []

  function showError(message: string): void {
    errorEl.textContent = message
    errorEl.hidden = !message
  }

  function paint(): void {
    listEl.innerHTML = ''
    if (items.length === 0) {
      renderEmpty(listEl, {
        avatar: true,
        title: '还没有收藏',
        hint: '在详情页点右上角的心，收进来的都在这儿',
        actionLabel: '去热门',
        onAction: () => { window.location.hash = '#/popular' },
      })
      return
    }
    for (const item of items) listEl.appendChild(card(item))
  }

  function card(item: FavoriteItem): HTMLElement {
    const cell = document.createElement('div')
    cell.className = 'fav-cell'

    const book = new AlbumCard()
    book.setData({
      id: item.album_id,
      title: item.title || `漫画 ${item.album_id}`,
      cover_url: item.cover_url || undefined,
      subtitle: item.added_at ? `收藏于 ${day(item.added_at)}` : '',
    })
    book.addEventListener('click', () => {
      window.location.hash = `#/album?id=${item.album_id}`
    })

    const del = document.createElement('button')
    del.type = 'button'
    del.className = 'fav-del'
    del.title = '取消收藏'
    del.setAttribute('aria-label', `取消收藏 ${item.title || item.album_id}`)
    del.appendChild(createIcon(icons.trash, { size: 14 }))
    // 删除按钮就贴在卡片里，别让点击冒泡上去（那就跳详情了）
    del.addEventListener('click', (ev) => {
      ev.stopPropagation()
      void remove(item, del)
    })

    cell.append(book, del)
    return cell
  }

  async function remove(item: FavoriteItem, btn: HTMLButtonElement): Promise<void> {
    const api = window.pywebview?.api
    if (!api) return
    btn.disabled = true
    try {
      await api.remove_favorite(item.album_id)
      showError('')
      // 本地数组同步删掉再重画：不重拉整张表，剩下的卡片不会闪一下
      items = items.filter((it) => it.album_id !== item.album_id)
      paint()
    } catch (err) {
      btn.disabled = false
      showError(`取消收藏失败：${String(err).replace(/^Error:\s*/, '')}`)
    }
  }

  async function load(): Promise<void> {
    if (!window.pywebview?.api) {
      renderError(listEl, 'pywebview api 还没就绪', () => void load())
      return
    }
    try {
      renderAlbumSkeleton(listEl, 6)
      items = await window.pywebview.api.get_favorites(200)
      showError('')
      paint()
    } catch (err) {
      renderError(listEl, String(err), () => void load())
    }
  }

  void load()

  return el
}

/** 收藏时间戳 → 2026-10-13（按本机时区） */
function day(addedAt: number): string {
  const d = new Date(addedAt * 1000)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
