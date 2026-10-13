import { AlbumCard } from '../components/album.js'

export function searchPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.innerHTML = `
    <h2>搜索专辑</h2>
    <input id="keyword" placeholder="输入关键词" />
    <button id="search-btn">搜索</button>
    <div class="album-list"></div>
  `

  const keywordInput = el.querySelector<HTMLInputElement>('#keyword')!
  const searchBtn = el.querySelector<HTMLButtonElement>('#search-btn')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!

  // 从 URL 参数恢复关键词
  if (params.q) keywordInput.value = params.q

  async function doSearch() {
    const keyword = keywordInput.value.trim()
    if (!keyword) {
      listEl.textContent = '请输入关键词'
      return
    }
    if (!window.pywebview?.api) {
      listEl.textContent = 'pywebview api 未就绪'
      return
    }
    try {
      listEl.textContent = '搜索中...'
      const data = await window.pywebview.api.search(keyword)
      renderAlbumList(data, listEl)
    } catch (err) {
      listEl.textContent = `搜索失败: ${String(err)}`
    }
  }

  searchBtn.addEventListener('click', doSearch)
  keywordInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch()
  })

  // 如果 URL 带了 q，自动搜一次
  if (params.q) doSearch()

  return el
}

function renderAlbumList(albums: AlbumSummary[], container: HTMLElement) {
  container.innerHTML = ''
    if (albums.length === 0) {
    container.innerHTML = '<p class="empty-hint">这个分类暂时没有上榜作品，换个时间或分类看看</p>'
    return
  }
  for (const item of albums) {
    const card = new AlbumCard()
    card.setData(item)
    container.appendChild(card)
  }
}