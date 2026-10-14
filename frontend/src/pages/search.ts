import { renderAlbumList } from '../components/album-list.js'
import { createPicker } from '../components/picker.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { createIcon, icons, morphIcon, setIcon } from '../components/icons.js'
import { onUnmount } from '../router.js'
import { loadState, pickKey, saveState } from '../store.js'
import { warmAlbumList } from '../prefetch.js'

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

// 搜索记录：只记用户真搜过的词，是界面记忆不是设置，走 localStorage（清缓存不动它）
const RECENT_KEY = 'search:recent'
const RECENT_MAX = 12

/** 读记录：老数据 / 手改过的 JSON 认不出来就当没记过；去空、无视大小写去重、超上限的砍掉 */
function loadRecent(): string[] {
  const raw = loadState<unknown>(RECENT_KEY, [])
  if (!Array.isArray(raw)) return []
  const out: string[] = []
  for (const item of raw) {
    if (typeof item !== 'string') continue
    const keyword = item.trim()
    if (!keyword || out.some((k) => k.toLowerCase() === keyword.toLowerCase())) continue
    out.push(keyword)
    if (out.length >= RECENT_MAX) break
  }
  return out
}

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
      <div class="search-recent" hidden></div>
      <div class="album-list"></div>
    </section>
  `

  const keywordInput = el.querySelector<HTMLInputElement>('#keyword')!
  const searchBtn = el.querySelector<HTMLButtonElement>('#search-btn')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const recentBox = el.querySelector<HTMLDivElement>('.search-recent')!
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

  // 最近搜索：一行 chips，点词直接重搜，✕ 删单条，右上「清空」删全部。
  // 只记关键词、不记范围 / 排序 —— 点 chip 用的是当前筛选条件（筛选行就在上面，看得见）
  let recent = loadRecent()

  function saveRecent(): void {
    saveState(RECENT_KEY, recent)
  }

  function paintRecent(): void {
    recentBox.innerHTML = ''
    recentBox.hidden = recent.length === 0
    if (!recent.length) return

    const head = document.createElement('div')
    head.className = 'recent-head'
    const title = document.createElement('span')
    title.className = 'recent-title'
    title.textContent = '最近搜索'
    const clear = document.createElement('button')
    clear.type = 'button'
    clear.className = 'recent-clear'
    clear.textContent = '清空'
    clear.addEventListener('click', () => {
      recent = []
      saveRecent()
      paintRecent()
      keywordInput.focus()
    })
    head.append(title, clear)

    const row = document.createElement('div')
    row.className = 'recent-row'
    for (const keyword of recent) {
      const chip = document.createElement('span')
      chip.className = 'recent-chip'

      const hit = document.createElement('button')
      hit.type = 'button'
      hit.className = 'recent-hit'
      hit.textContent = keyword
      hit.title = keyword
      hit.addEventListener('click', () => {
        keywordInput.value = keyword
        void doSearch()
      })

      const del = document.createElement('button')
      del.type = 'button'
      del.className = 'recent-del'
      del.title = `删除「${keyword}」`
      del.setAttribute('aria-label', `删除「${keyword}」`)
      del.appendChild(createIcon(icons.close, { size: 12 }))
      del.addEventListener('click', () => {
        recent = recent.filter((item) => item !== keyword)
        saveRecent()
        paintRecent()
      })

      chip.append(hit, del)
      row.appendChild(chip)
    }
    recentBox.append(head, row)
  }

  /** 记一次搜索：同一个词（无视大小写）挪到最前，不重复占位 */
  function rememberRecent(keyword: string): void {
    recent = [keyword, ...recent.filter((item) => item.toLowerCase() !== keyword.toLowerCase())]
      .slice(0, RECENT_MAX)
    saveRecent()
    paintRecent()
  }

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
    rememberRecent(keyword)
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
      // 封面 + 标题已经铺在屏幕上了，详情缓存丢后台慢慢预热
      warmAlbumList(data.map((item) => item.id))
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

  paintRecent()

  // 如果 URL 带了 q，自动搜一次
  if (params.q) void doSearch()
  else {
    renderEmpty(listEl, {
      avatar: true,
      title: '想找什么漫画？',
      hint: recent.length
        ? '输入关键词后按回车，或者点上面的最近搜索'
        : '输入关键词后按回车；搜作者名把范围切到「作者」更准',
    })
    // 路由要等这个函数返回后才把节点挂上，所以聚焦得等下一帧
    requestAnimationFrame(() => keywordInput.focus())
  }

  return el
}
