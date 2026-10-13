import { renderAlbumList } from '../components/album-list.js'
import { createPicker } from '../components/picker.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { icons, morphIcon, setIcon } from '../components/icons.js'
import { onUnmount } from '../router.js'
import { loadState, pickKey, saveState } from '../store.js'

// 搜索范围：对应后端 search() 的 scope（五个 search_* 方法共用同一套参数）
const SCOPES: { key: SearchScope; label: string }[] = [
  { key: 'site', label: '站内' },
  { key: 'work', label: '作品名' },
  { key: 'author', label: '作者' },
  { key: 'tag', label: '标签' },
  { key: 'actor', label: '角色' },
]

// 搜索排序：对应后端 search() 的 order_by
const SORTS: { key: SortOrder; label: string }[] = [
  { key: 'latest', label: '最新' },
  { key: 'views', label: '观看' },
  { key: 'likes', label: '收藏' },
  { key: 'score', label: '评分' },
]

const SCOPE_KEYS = SCOPES.map((item) => item.key)
const SORT_KEYS = SORTS.map((item) => item.key)

interface SearchPrefs {
  scope: SearchScope
  sort: SortOrder
}

/** 范围 / 排序的来源：URL 参数（手改的地址、老链接说了算）> 上次用过的 > 默认值 */
function loadPrefs(params: Record<string, string>): SearchPrefs {
  const saved = loadState<Partial<SearchPrefs>>('search', {})
  return {
    scope: pickKey(params.scope ?? saved.scope, SCOPE_KEYS, 'site'),
    sort: pickKey(params.sort ?? saved.sort, SORT_KEYS, 'latest'),
  }
}

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
      <div class="search-filters">
        <span class="search-filters-hint">范围</span>
        <div class="scope-slot"></div>
        <span class="search-filters-hint">排序</span>
        <div class="sort-slot"></div>
      </div>
      <div class="album-list"></div>
    </section>
  `

  const keywordInput = el.querySelector<HTMLInputElement>('#keyword')!
  const searchBtn = el.querySelector<HTMLButtonElement>('#search-btn')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const searchIco = setIcon(searchBtn, 'morph-icon', icons.search)

  const prefs = loadPrefs(params)
  let scope: SearchScope = prefs.scope
  let sort: SortOrder = prefs.sort
  const remember = (): void => saveState('search', { scope, sort })

  const scopePicker = createPicker(SCOPES, (key) => {
    scope = key
    scopePicker.set(key)
    remember()
    // 已经敲过关键词就按新条件重搜一遍，省得再点一次「搜索」
    if (keywordInput.value.trim()) void doSearch()
  })
  scopePicker.set(scope)
  el.querySelector('.scope-slot')!.appendChild(scopePicker.el)

  const sortPicker = createPicker(SORTS, (key) => {
    sort = key
    sortPicker.set(key)
    remember()
    if (keywordInput.value.trim()) void doSearch()
  })
  sortPicker.set(sort)
  el.querySelector('.sort-slot')!.appendChild(sortPicker.el)

  const closeMenus = (): void => { scopePicker.close(); sortPicker.close() }
  const onKey = (event: KeyboardEvent): void => { if (event.key === 'Escape') closeMenus() }
  document.addEventListener('click', closeMenus)
  window.addEventListener('keydown', onKey)
  onUnmount(() => {
    document.removeEventListener('click', closeMenus)
    window.removeEventListener('keydown', onKey)
  })

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
      const data = await window.pywebview.api.search(keyword, 1, scope, sort)
      searchIco.classList.remove('spin')
      morphIcon(searchIco, data.length ? icons.searchDone : icons.search)
      renderAlbumList(data, listEl, {
        icon: '🔍',
        title: `没搜到「${keyword}」`,
        hint: '换个关键词或换个搜索范围，也可以去热门里逛逛',
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
    renderEmpty(listEl, { avatar: true, title: '想找什么漫画？', hint: '输入关键词后按回车；搜作者名把范围切到「作者」更准' })
    // 路由要等这个函数返回后才把节点挂上，所以聚焦得等下一帧
    requestAnimationFrame(() => keywordInput.focus())
  }

  return el
}
