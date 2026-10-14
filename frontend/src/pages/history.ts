// pages/history.ts
// 最近阅读：一部漫画一条（取最近读的那一话），点卡片进详情页。
// 每条一个 ✕、页头一个「清空」——动的是 data/app.db 的 history 表，
// 收藏与离线副本都不碰（那两样是"资产"，阅读记录只代表"看到哪儿了"）。
import { AlbumCard } from '../components/album.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { createIcon, icons } from '../components/icons.js'
import type { HistoryItem } from '../types.js'

export function historyPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'history-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">最近阅读</h1>
      <p class="page-sub">一部漫画一条，按最近读过的顺序排</p>
      <div class="page-actions">
        <button type="button" class="mini-btn danger clear-history-btn">
          <morph-icon size="14" stroke-width="1.8"></morph-icon><span>清空记录</span>
        </button>
      </div>
    </header>
    <p class="history-status" hidden></p>
    <div class="album-list"></div>
  `

  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const statusEl = el.querySelector<HTMLElement>('.history-status')!
  const clearBtn = el.querySelector<HTMLButtonElement>('.clear-history-btn')!
  const clearIco = el.querySelector<HTMLElement>('.clear-history-btn morph-icon')!
  ;(clearIco as HTMLElement & { icon: unknown }).icon = icons.trash
  clearIco.setAttribute('aria-hidden', 'true')
  const api = () => window.pywebview?.api

  function say(message: string): void {
    statusEl.textContent = message
    statusEl.hidden = !message
  }

  /** 一条记录一张卡：卡片本体走 AlbumCard，右上角自己加一个 ✕ */
  function card(item: HistoryItem): HTMLElement {
    const cell = document.createElement('div')
    cell.className = 'dl-cell'
    const book = new AlbumCard()
    book.setData({
      id: item.album_id,
      title: item.title || `漫画 ${item.album_id}`,
      cover_url: item.cover_url || undefined,
      subtitle: `读到第 ${item.page_index + 1} 页`,
    })
    book.addEventListener('click', () => {
      window.location.hash = `#/album?id=${item.album_id}`
    })
    const del = document.createElement('button')
    del.type = 'button'
    del.className = 'card-del'
    del.title = '从最近阅读里删掉这部'
    del.appendChild(createIcon(icons.close, { size: 13 }))
    del.addEventListener('click', (ev) => {
      ev.stopPropagation()      // 别冒泡成"进详情"
      void remove(item)
    })
    book.append(del)
    cell.appendChild(book)
    return cell
  }

  async function remove(item: HistoryItem): Promise<void> {
    const current = api()
    if (!current?.remove_history) {
      say('pywebview api 还没就绪')
      return
    }
    try {
      await current.remove_history(item.album_id)
      say('已从最近阅读里删掉')
      await load()
    } catch (err) {
      say('删不掉：' + String(err).replace(/^Error:\s*/, ''))
    }
  }

  clearBtn.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.clear_history) {
        say('pywebview api 还没就绪')
        return
      }
      if (!window.confirm('清空最近阅读？阅读进度会一起没（收藏和离线下载不动）')) return
      try {
        const res = await current.clear_history()
        say(`已清空 ${res.removed} 条记录`)
        await load()
      } catch (err) {
        say('清空失败：' + String(err).replace(/^Error:\s*/, ''))
      }
    })()
  })

  async function load(): Promise<void> {
    if (!api()) {
      renderError(listEl, 'pywebview api 还没就绪', () => void load())
      return
    }
    try {
      renderAlbumSkeleton(listEl, 6)
      const items = await api()!.get_history(60)
      render(items)
    } catch (err) {
      renderError(listEl, String(err), () => void load())
    }
  }

  function render(items: HistoryItem[]): void {
    listEl.innerHTML = ''
    if (items.length === 0) {
      renderEmpty(listEl, {
        avatar: true,
        title: '还没有阅读记录',
        hint: '去「热门」里挑一本，读过之后这里就有了',
        actionLabel: '去热门',
        onAction: () => { window.location.hash = '#/popular' },
      })
      return
    }
    for (const item of items) listEl.appendChild(card(item))
    clearBtn.hidden = false
  }

  void load()

  return el
}
