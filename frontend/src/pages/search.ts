import { renderAlbumList } from '../components/album-list.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'

export function searchPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.className = 'search-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">搜索</h1>
      <p class="page-sub">输入关键词，回车或点「搜索」</p>
    </header>
    <div class="search-bar">
      <input id="keyword" placeholder="输入关键词" />
      <button id="search-btn">搜索</button>
    </div>
    <div class="album-list"></div>
  `

  const keywordInput = el.querySelector<HTMLInputElement>('#keyword')!
  const searchBtn = el.querySelector<HTMLButtonElement>('#search-btn')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!

  // 从 URL 参数恢复关键词
  if (params.q) keywordInput.value = params.q

  function goPopular(): void {
    window.location.hash = '#/popular'
  }

  async function doSearch(): Promise<void> {
    const keyword = keywordInput.value.trim()
    if (!keyword) {
      renderEmpty(listEl, { icon: '🔍', title: '先输入关键词', hint: '作者名、作品名都行' })
      keywordInput.focus()
      return
    }
    if (!window.pywebview?.api) {
      renderError(listEl, 'pywebview api 还没就绪', () => void doSearch())
      return
    }
    try {
      renderAlbumSkeleton(listEl, 5)
      const data = await window.pywebview.api.search(keyword)
      renderAlbumList(data, listEl, {
        icon: '🔍',
        title: `没搜到「${keyword}」`,
        hint: '换个关键词，或者去热门里逛逛',
        actionLabel: '去热门',
        onAction: goPopular,
      })
    } catch (err) {
      renderError(listEl, String(err), () => void doSearch())
    }
  }

  searchBtn.addEventListener('click', () => void doSearch())
  keywordInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') void doSearch()
  })

  // 如果 URL 带了 q，自动搜一次
  if (params.q) void doSearch()
  else renderEmpty(listEl, { icon: '🔍', title: '想找什么漫画？', hint: '输入关键词后按回车' })

  return el
}