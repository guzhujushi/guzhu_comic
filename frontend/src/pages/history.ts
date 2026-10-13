import { renderAlbumList } from '../components/album-list.js'

/** 最近阅读：用的是阅读时存下的 history 表，点卡片进详情页再决定读哪一话 */
export function historyPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'history-page'
  el.innerHTML = `
    <h2>最近阅读</h2>
    <div class="album-list"></div>
  `

  const listEl = el.querySelector<HTMLDivElement>('.album-list')!

  void (async () => {
    if (!window.pywebview?.api) {
      listEl.innerHTML = '<p class="empty-hint">pywebview api 未就绪</p>'
      return
    }
    try {
      listEl.textContent = '加载中...'
      const items = await window.pywebview.api.get_history(60)
      renderAlbumList(
        items.map((item) => ({
          id: item.album_id,
          title: item.title || `漫画 ${item.album_id}`,
          cover_url: item.cover_url,
          subtitle: `读到第 ${item.page_index + 1} 页`,
        })),
        listEl,
        '还没有阅读记录，去「热门」里挑一本吧',
      )
    } catch (err) {
      listEl.innerHTML = `<p class="empty-hint">加载失败: ${String(err)}</p>`
    }
  })()

  return el
}
