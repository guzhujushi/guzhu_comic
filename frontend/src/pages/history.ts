import { renderAlbumList } from '../components/album-list.js'
import { renderAlbumSkeleton, renderError } from '../components/states.js'

/** 最近阅读：用的是阅读时存下的 history 表，点卡片进详情页再决定读哪一话 */
export function historyPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'history-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">最近阅读</h1>
      <p class="page-sub">一部漫画一条，按最近读过的顺序排</p>
    </header>
    <div class="album-list"></div>
  `

  const listEl = el.querySelector<HTMLDivElement>('.album-list')!

  async function load(): Promise<void> {
    if (!window.pywebview?.api) {
      renderError(listEl, 'pywebview api 还没就绪', () => void load())
      return
    }
    try {
      renderAlbumSkeleton(listEl, 6)
      const items = await window.pywebview.api.get_history(60)
      renderAlbumList(
        items.map((item) => ({
          id: item.album_id,
          title: item.title || `漫画 ${item.album_id}`,
          cover_url: item.cover_url,
          subtitle: `读到第 ${item.page_index + 1} 页`,
        })),
        listEl,
        {
          icon: '🕒',
          title: '还没有阅读记录',
          hint: '去「热门」里挑一本，读过之后这里就有了',
          actionLabel: '去热门',
          onAction: () => { window.location.hash = '#/popular' },
        },
      )
    } catch (err) {
      renderError(listEl, String(err), () => void load())
    }
  }

  void load()

  return el
}