import { renderAlbumList } from '../components/album-list.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { icons, morphIcon, setIcon } from '../components/icons.js'

export function searchPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.className = 'search-page glow-behind'
  el.innerHTML = `
    <section class="glass search-shell">
      <header class="page-head">
        <h1 class="page-title">搜索</h1>
        <p class="page-sub">输入关键词，回车或点「搜索」</p>
      </header>
      <div class="search-bar">
        <input id="keyword" placeholder="输入关键词" />
        <button id="search-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>搜索</span></button>
      </div>
      <div class="album-list"></div>
    </section>
  `

  const keywordInput = el.querySelector<HTMLInputElement>('#keyword')!
  const searchBtn = el.querySelector<HTMLButtonElement>('#search-btn')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const searchIco = setIcon(searchBtn, 'morph-icon', icons.search)

  // 从 URL 参数恢复关键词
  if (params.q) keywordInput.value = params.q

  function goPopular(): void {
    window.location.hash = '#/popular'
  }

  async function doSearch(): Promise<void> {
    const keyword = keywordInput.value.trim()
    if (!keyword) {
      renderEmpty(listEl, { avatar: true, title: '先输入关键词', hint: '作者名、作品名都行' })
      keywordInput.focus()
      return
    }
    if (!window.pywebview?.api) {
      renderError(listEl, 'pywebview api 还没就绪', () => void doSearch())
      return
    }
    try {
      renderAlbumSkeleton(listEl, 5)
      // 搜索时放大镜变成转圈的加载图标，回来再变回放大镜 / 打勾
      morphIcon(searchIco, icons.searchBusy)
      searchIco.classList.add('spin')
      const data = await window.pywebview.api.search(keyword)
      searchIco.classList.remove('spin')
      morphIcon(searchIco, data.length ? icons.searchDone : icons.search)
      renderAlbumList(data, listEl, {
        icon: '🔍',
        title: `没搜到「${keyword}」`,
        hint: '换个关键词，或者去热门里逛逛',
        actionLabel: '去热门',
        onAction: goPopular,
      })
    } catch (err) {
      searchIco.classList.remove('spin')
      morphIcon(searchIco, icons.search)
      renderError(listEl, String(err), () => void doSearch())
    }
  }

  searchBtn.addEventListener('click', () => void doSearch())
  keywordInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') void doSearch()
  })

  // 如果 URL 带了 q，自动搜一次
  if (params.q) void doSearch()
  else {
    renderEmpty(listEl, { avatar: true, title: '想找什么漫画？', hint: '输入关键词后按回车' })
    // 路由要等这个函数返回后才把节点挂上，所以聚焦得等下一帧
    requestAnimationFrame(() => keywordInput.focus())
  }

  return el
}