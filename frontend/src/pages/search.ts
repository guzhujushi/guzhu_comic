import { renderAlbumList } from '../components/album-list.js'
import { createPicker } from '../components/picker.js'
import { createRecommendSection } from '../components/recommend.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { createIcon, icons, morphIcon, setIcon } from '../components/icons.js'
import { onUnmount, replaceHash } from '../router.js'
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

// 搜索记录搬进 data/app.db（后端那张 search_log 表）：推荐要知道"搜过什么、搜了几次、
// 什么时候搜的"，这三样只有后端算得了。所以不存两份，chips 直接读库（清缓存不动它）
const RECENT_MAX = 12

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
  // 推荐段：铺在结果列表下面（还没搜过时也在）；铺不出来就整段不出现
  const rec = createRecommendSection('search')
  el.querySelector('.search-shell')!.appendChild(rec.el)
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
  let recent: string[] = []
  let idle = !params.q     // 还没搜过：空状态那句提示等记录读回来再定稿

  /** 记录（真相在后端库里）读回来重画 chips；读不出来就当没记过，搜索照用 */
  async function loadRecent(): Promise<void> {
    const bridge = window.pywebview?.api
    if (!bridge?.get_search_log) return
    try {
      recent = (await bridge.get_search_log(RECENT_MAX)).map((row) => row.keyword)
      paintRecent()
    } catch {
      /* 读不出来就当没记过 */
    }
  }

  /** 往后端记一笔（记录也是推荐画像的输入；失败不影响这次搜索） */
  function logSearch(keyword: string): void {
    const bridge = window.pywebview?.api
    if (!bridge?.log_search) return
    void bridge.log_search(keyword, scope).catch(() => undefined)
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
      paintRecent()
      keywordInput.focus()
      const bridge = window.pywebview?.api
      if (bridge?.clear_search_log) void bridge.clear_search_log().catch(() => undefined)
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
        paintRecent()
        const bridge = window.pywebview?.api
        if (bridge?.remove_search_log) void bridge.remove_search_log(keyword).catch(() => undefined)
      })

      chip.append(hit, del)
      row.appendChild(chip)
    }
    recentBox.append(head, row)
  }

  /** 记一次搜索：本地先把词挪到最前（chips 立刻更新），库里那份记累加次数与时间 */
  function rememberRecent(keyword: string): void {
    recent = [keyword, ...recent.filter((item) => item.toLowerCase() !== keyword.toLowerCase())]
      .slice(0, RECENT_MAX)
    paintRecent()
    logSearch(keyword)
  }

  // 从 URL 参数恢复关键词
  if (params.q) keywordInput.value = params.q

  function goPopular(): void {
    window.location.hash = '#/popular'
  }

  /**
   * 把"现在搜的是什么"写进地址栏：`#/search?q=…`。
   *
   * 用 replaceState 而不是赋 hash，两个原因：
   *  ① 换关键词不该在历史里堆一串（`?q=a` → `?q=ab` → …），想退出去得按好几下；
   *  ② 从详情页点「返回」时回到的就是这条**带关键词**的记录 —— 挂载时按 `params.q` 重搜一遍，
   *     结果和输入框都还在（用户报的 bug 就是这个：以前地址里没词，返回只剩一个空搜索页）。
   * 赋 hash 还会顺带触发 hashchange 把整页重渲染一遍，那是白跑 —— 屏幕上的东西已经对了。
   */
  function syncUrl(keyword: string): void {
    if (!keyword) {
      if (window.location.hash !== '#/search') replaceHash('#/search')
      return
    }
    const query = [`q=${encodeURIComponent(keyword)}`]
    // 范围 / 排序不是默认值时一并带上（`&scope=tag`）：详情页的标签、作者点进来就是这种地址。
    // 不带的话，返回 / 刷新会按 localStorage 里那份"上次用的条件"重搜，结果跟当时那批对不上。
    if (scope !== 'site') query.push(`scope=${scope}`)
    if (sort !== 'latest') query.push(`sort=${sort}`)
    const next = `#/search?${query.join('&')}`
    if (window.location.hash !== next) replaceHash(next)
  }

  /**
   * restore=true 是"按地址栏还原"那条路（从详情返回 / 刷新 / 直接打开链接）：这种情况**不记搜索记录** ——
   * 记录里的次数与时间是推荐画像的输入，跟着返回键刷上去就失真了。
   */
  async function doSearch(restore = false): Promise<void> {
    const keyword = keywordInput.value.trim()
    if (!keyword) {
      syncUrl('')   // 词清空了就别在地址里留着上一次的，免得刷新 / 返回又冒出一个搜过的东西
      renderEmpty(listEl, { avatar: true, title: '先输入关键词', hint: '作者名、作品名都行' })
      keywordInput.focus()
      return
    }
    idle = false
    if (!window.pywebview?.api) {
      renderError(listEl, 'pywebview api 还没就绪', () => void doSearch())
      return
    }
    if (!restore) rememberRecent(keyword)
    syncUrl(keyword)
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

  // 老版本把搜索记录存在 localStorage（guzhu:search:recent）：搬进 data/app.db 之后
  // 顺手把那个键删掉，免得留一份跟库里对不上的旧数据
  try {
    window.localStorage.removeItem('guzhu:search:recent')
  } catch {
    /* 存储被禁用就算了 */
  }

  /** 还没搜过时的空状态：有记录就提示"点上面的最近搜索" */
  function paintIdle(): void {
    renderEmpty(listEl, {
      avatar: true,
      title: '想找什么漫画？',
      hint: recent.length
        ? '输入关键词后按回车，或者点上面的最近搜索'
        : '输入关键词后按回车；搜作者名把范围切到「作者」更准',
    })
  }

  // 记录是异步读回来的（真相在后端库里），读完再把这句提示定稿
  void loadRecent().then(() => {
    if (idle) paintIdle()
  })

  // 推荐段跟首页同一套（一期不吃本次关键词），进来就开始铺
  rec.load()

  // 如果 URL 带了 q，自动搜一次（从详情返回 / 刷新 / 手改地址都走这条，不记新记录）
  if (params.q) {
    void doSearch(true)
  } else {
    paintIdle()
    // 路由要等这个函数返回后才把节点挂上，所以聚焦得等下一帧
    requestAnimationFrame(() => keywordInput.focus())
  }

  return el
}
