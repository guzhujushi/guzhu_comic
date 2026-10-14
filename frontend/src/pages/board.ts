// pages/board.ts
// 热门榜单：hero（当前分类最火三部）+ 分类标签条 + 面板，
// 「#/popular」是全部那一页，「#/category?c=xx」是某个分类那一页，两边共用这一套。
import { renderAlbumList } from '../components/album-list.js'
import { createIcon, icons, setIcon } from '../components/icons.js'
import { createPicker } from '../components/picker.js'
import { createRecommendSection } from '../components/recommend.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { renderHero, renderHeroSkeleton } from '../components/hero.js'
import type { HeroHandle } from '../components/hero.js'
import { onUnmount } from '../router.js'
import { warmAlbumList } from '../prefetch.js'
import { splashReady } from '../splash.js'
import { bridgeCall, waitForApi } from '../webstatus.js'
import { loadState, pickKey, saveState } from '../store.js'
import type { AlbumSummary } from '../types.js'

const RANGES: { key: RankRange; label: string }[] = [
  { key: 'day', label: '日榜' },
  { key: 'week', label: '周榜' },
  { key: 'month', label: '月榜' },
]

/** 榜单排序：对应后端 get_ranking() 的 order_by */
const SORTS: { key: SortOrder; label: string }[] = [
  { key: 'views', label: '按观看' },
  { key: 'likes', label: '按收藏' },
  { key: 'score', label: '按评分' },
  { key: 'images', label: '按图片数' },
  { key: 'comments', label: '按评论' },
  { key: 'latest', label: '按最新' },
]

/** 标签条上的分类，顺序就是显示顺序 */
const CATEGORY_LABELS: Record<ComicCategory, string> = {
  all: '全部',
  doujin: '同人',
  single: '单本',
  short: '短篇',
  hanman: '韩漫',
  meiman: '美漫',
}

export const CATEGORY_KEYS = Object.keys(CATEGORY_LABELS) as ComicCategory[]

const RANGE_KEYS = RANGES.map((item) => item.key)
const SORT_KEYS = SORTS.map((item) => item.key)

/** 一行放几张：卡片按 148px 上下算，面板越宽放越多 */
const CARD_W = 148
const CARD_GAP = 16

function colsFor(inner: number): number {
  if (inner <= 0) return 5
  return Math.max(2, Math.floor((inner + CARD_GAP) / (CARD_W + CARD_GAP)))
}

export interface BoardPrefs {
  range: RankRange
  sort: SortOrder
}

/** 上次看的榜单 / 排序：刷新页面、重开窗口都记得住，认不出的值回退默认 */
function loadPrefs(): BoardPrefs {
  const saved = loadState<Partial<BoardPrefs>>('popular', {})
  return {
    range: pickKey(saved.range, RANGE_KEYS, 'week'),
    sort: pickKey(saved.sort, SORT_KEYS, 'views'),
  }
}

/** 首页这一刻会用的榜单条件：闪屏预热要跟它完全一致，所以由这里出这一份（见 main.ts） */
export function homePrefs(): BoardPrefs {
  return loadPrefs()
}

/** 首页那一页：hero 之下的分类横条，一个分类一段 */
interface CatRow {
  key: ComicCategory
  el: HTMLElement
  rowEl: HTMLElement
  /** null = 还没拿到（铺骨架），[] = 这个分类这期没有 */
  items: AlbumSummary[] | null
  error: string | null
  /** 已经挂过"进视口演一次入场"，重排时别再演 */
  armed: boolean
  /** 失败已经自动重来过一次，别再没完没了地重试 */
  retried: boolean
}

export function boardPage(category: ComicCategory): HTMLElement {
  const home = category === 'all'   // 全部那一页：面板里铺各个分类的横条
  const el = document.createElement('div')
  el.className = 'board-page'
  el.innerHTML = `
    ${home ? '' : '<div class="cat-back"><button class="back-btn" type="button"><morph-icon size="15" stroke-width="1.8"></morph-icon><span>返回</span></button></div>'}
    <header class="page-head">
      <h1 class="page-title"></h1>
    </header>
    ${home ? `<div class="home-search glow-behind">
      <img class="home-avatar" src="/apple-touch-icon.png" alt="" />
      <button type="button" class="search-entry glass">
        <morph-icon class="home-search-ico" size="16" stroke-width="1.8" aria-hidden="true"></morph-icon>
        <span class="search-entry-text">搜作品、作者</span>
        <kbd>/</kbd>
      </button>
    </div>` : ''}
    <div class="hero"></div>
    <div class="board">
      <div class="board-head">
        <div class="board-tabs"></div>
        <div class="board-tools">
          <div class="range-slot"></div>
          <div class="sort-slot"></div>
        </div>
      </div>
      <div class="board-panel"></div>
    </div>
  `
  el.querySelector<HTMLElement>('.page-title')!.textContent = home ? '热门榜单' : CATEGORY_LABELS[category]

  const heroEl = el.querySelector<HTMLDivElement>('.hero')!
  const tabsEl = el.querySelector<HTMLDivElement>('.board-tabs')!
  const panelEl = el.querySelector<HTMLDivElement>('.board-panel')!

  if (home) setIcon(el, '.home-search-ico', icons.search)
  if (!home) {
    setIcon(el, '.back-btn morph-icon', icons.back)
    el.querySelector<HTMLButtonElement>('.back-btn')!.addEventListener('click', () => history.back())
  }

  // 分类标签条：当前分类就是"贴"在下面面板上的那一个；点别的分类跳到别的页
  for (const key of CATEGORY_KEYS) {
    const tab = document.createElement('button')
    tab.type = 'button'
    tab.className = 'board-tab'
    tab.textContent = CATEGORY_LABELS[key]
    if (key === category) tab.classList.add('active')
    tab.addEventListener('click', () => {
      if (key === category) return
      window.location.hash = key === 'all' ? '#/popular' : `#/category?c=${key}`
    })
    tabsEl.appendChild(tab)
  }

  // 面板里：首页铺"别的分类"各一行，分类页铺自己的整页列表
  const boardMsgEl = document.createElement('div')
  boardMsgEl.className = 'board-empty'
  boardMsgEl.hidden = true
  panelEl.appendChild(boardMsgEl)

  // 推荐段：面板里第一段（各分类横条之前）。铺不出来就整段不出现（见 recommend.ts）
  // 首页这一段就在 hero 下面：把 hero 那几部排除掉，同一部书别上下各出现一次（2026-10-14）
  const rec = home ? createRecommendSection('home', () => heroIds) : null
  if (rec) panelEl.insertBefore(rec.el, boardMsgEl.nextSibling)

  const rows: CatRow[] = []
  const gridEl = document.createElement('div')
  const moreEl = document.createElement('div')
  moreEl.className = 'load-more'

  if (home) {
    for (const key of CATEGORY_KEYS) {
      if (key === 'all') continue          // 全部就是这一页本身，不在下面再来一段
      const section = document.createElement('section')
      section.className = 'cat-section reveal'
      const head = document.createElement('div')
      head.className = 'cat-head'
      const name = document.createElement('h2')
      name.className = 'cat-name'
      name.textContent = CATEGORY_LABELS[key]
      const more = document.createElement('button')
      more.type = 'button'
      more.className = 'cat-more'
      more.textContent = '更多'
      more.appendChild(createIcon(icons.next, { size: 14 }))
      more.addEventListener('click', () => { window.location.hash = `#/category?c=${key}` })
      head.append(name, more)
      const row = document.createElement('div')
      row.className = 'album-list cat-row'
      section.append(head, row)
      panelEl.appendChild(section)
      rows.push({ key, el: section, rowEl: row, items: null, error: null, armed: false, retried: false })
    }
  } else {
    gridEl.className = 'album-list reveal'
    panelEl.append(gridEl, moreEl)
  }

  const prefs = loadPrefs()
  let current: BoardPrefs = prefs
  let hero: HeroHandle | null = null
  let token = 0                 // 每换一次条件加一，晚回来的旧结果直接丢
  let dead = false              // 页面已经切走：晚醒的定时器别再重新发起请求
  let retries = 0               // 整页失败自动重试的次数（成功后清零）
  let cols = 5
  let state: 'loading' | 'ready' | 'empty' | 'error' = 'loading'
  let errorText = ''
  let heroIds: string[] = []   // hero 那三部的 ID，跟横条一起送去预热详情

  // 分类页的整页列表：第 1 页的前三部已经进了 hero，从第 4 部接着铺
  const cards: AlbumSummary[] = []
  let page = 0
  let done = false
  let busy = false

  const rangePicker = createPicker(RANGES, (key) => { void load(key, current.sort) })
  const sortPicker = createPicker(SORTS, (key) => { void load(current.range, key) })
  el.querySelector('.range-slot')!.appendChild(rangePicker.el)
  el.querySelector('.sort-slot')!.appendChild(sortPicker.el)

  // 卡片虚化入场：面板进视口那一下亮出来，每张错开一点
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const reveal = calm || !('IntersectionObserver' in window) ? null : new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue
      entry.target.classList.add('in')
      reveal!.unobserve(entry.target)
    }
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.05 })

  /** 让这一块"进视口时演一次虚化入场"；已经演过的就别重演（重排会闪） */
  function armReveal(target: HTMLElement): void {
    target.classList.remove('in')
    if (!reveal) {
      target.classList.add('in')
      return
    }
    reveal.observe(target)
    // 兜底：IntersectionObserver 得等窗口真的在绘制才会回调（窗口刚起来还没画第一帧、
    // 被别的窗口整个盖住的时候是不回调的），那样首页就会一直停在模糊态、看着像没加载。
    // 所以过一小会儿自己量一次，在视口里的就直接亮出来。
    for (const delay of [400, 1500]) {
      window.setTimeout(() => {
        if (!document.contains(target)) return
        revealSoon(target)
      }, delay)
    }
  }

  /** 兜底用：这一刻在视口里就亮出来，还在屏幕外的交给观察器（滚动时再演） */
  function revealSoon(target: HTMLElement): void {
    if (target.classList.contains('in')) return
    const box = target.getBoundingClientRect()
    const height = window.innerHeight || document.documentElement.clientHeight
    if (box.top < height && box.bottom > 0) {
      reveal?.unobserve(target)
      target.classList.add('in')
    }
  }

  /**
   * 窗口从"没在画"（最小化 / 被别的窗口整个盖住）回到前台：
   * 把还没亮的横条补亮；页面要是还停在错误上，就当用户"切页回来"了，自己重来一次。
   */
  function recover(): void {
    for (const row of rows) {
      if (row.armed) revealSoon(row.el)
    }
    if (!home && state === 'ready') revealSoon(gridEl)
    if (state === 'error' || heroEl.querySelector('.hero-error') !== null) {
      retries = 0                     // 人回来了，再给两次自动重试的机会
      void load(current.range, current.sort)
    }
  }

  const onVisible = (): void => {
    if (document.visibilityState === 'visible') recover()
  }
  document.addEventListener('visibilitychange', onVisible)
  window.addEventListener('focus', recover)

  /** 卡片编号写进 --i，CSS 拿它错开每一张的入场延迟 */
  function stagger(container: HTMLElement): void {
    Array.from(container.children).forEach((child, i) => {
      (child as HTMLElement).style.setProperty('--i', String(i))
    })
  }

  function paintRow(row: CatRow): void {
    if (row.error !== null) {
      row.el.hidden = false
      renderError(row.rowEl, row.error, () => {
        row.items = null
        row.error = null
        paintRow(row)
        void fillRow(row, token)
      })
      return
    }
    if (row.items === null) {
      row.el.hidden = false
      renderAlbumSkeleton(row.rowEl, cols)
      return
    }
    const items = row.items.slice(0, cols)
    if (items.length === 0) {
      row.el.hidden = true
      row.rowEl.innerHTML = ''
      return
    }
    row.el.hidden = false
    renderAlbumList(items, row.rowEl)
    stagger(row.rowEl)
    // 真卡片铺好了再挂入场：别在骨架阶段就把它演掉
    if (!row.armed) {
      row.armed = true
      armReveal(row.el)
    }
  }

  function paintGrid(): void {
    if (cards.length === 0) {
      renderEmpty(gridEl, {
        icon: '🎬',
        title: '这个分类这期就这几部',
        hint: '都在上面的轮播里了，换个日 / 周 / 月或者换个排序再看看',
      })
      moreEl.innerHTML = ''
      return
    }
    renderAlbumList(cards, gridEl)
    stagger(gridEl)
    moreEl.innerHTML = ''
    if (done) {
      const hint = document.createElement('span')
      hint.className = 'load-hint'
      hint.textContent = '到底了'
      moreEl.appendChild(hint)
      return
    }
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.textContent = busy ? '加载中…' : '加载更多'
    btn.disabled = busy
    btn.addEventListener('click', () => void loadMore())
    moreEl.appendChild(btn)
  }

  /** 面板宽度能放几张卡片（首页那一列一列的行要用） */
  function applyCols(): void {
    panelEl.style.setProperty('--cols', String(cols))
  }

  function paintPanel(): void {
    if (state === 'loading') {
      for (const row of rows) paintRow(row)
      if (!home) {
        renderAlbumSkeleton(gridEl, 10)
        moreEl.innerHTML = ''
      }
      return
    }
    if (state !== 'ready') {      // empty / error：面板里只留顶部那句话，别留着骨架占地方
      for (const row of rows) {
        row.el.hidden = true
        row.rowEl.innerHTML = ''
      }
      gridEl.innerHTML = ''
      moreEl.innerHTML = ''
      return
    }
    if (home) {
      for (const row of rows) paintRow(row)
      return
    }
    paintGrid()
  }

  /**
   * 把「这一刻摆在屏幕上」的作品交给后端预热详情缓存：封面 + 标题先铺，详情随后慢慢来。
   * 只送真的铺出来的那几张（一行只铺 --cols 张、分类页就送已铺出来的那些）。
   * 每次重发整份清单没关系 —— 后端认过的不要，一次也只预热有限几部。
   */
  function warmVisible(): void {
    const ids = [...heroIds]
    for (const row of rows) {
      if (row.items) ids.push(...row.items.slice(0, cols).map((item) => item.id))
    }
    for (const card of cards) ids.push(card.id)
    warmAlbumList(ids)
  }

  /**
   * hero 已经摆在最上面了，下面这些横条里就别再出现同一部（2026-10-14 用户要求）。
   * 在**取回来的整页里**先剔掉、再切前 `--cols` 张（切完再过滤的话，一条横条会短一截，
   * 看着像少了一部）；多出来的候选正好把空位补上。
   */
  function dropHero(items: AlbumSummary[]): AlbumSummary[] {
    if (heroIds.length === 0) return items
    const skip = new Set(heroIds)
    return items.filter((item) => !skip.has(item.id))
  }

  /** 一个分类的请求：首页各拉各的，谁先回来谁先铺，不互相等 */
  async function fillRow(row: CatRow, my: number): Promise<void> {
    try {
      const items = await bridgeCall('get_ranking', [current.range, row.key, 1, current.sort])
      if (my !== token) return
      row.items = dropHero(items)
    } catch (err) {
      if (my !== token) return
      // 图源第一次请求容易抖（客户端刚起来 / 缓存是空的），自动补一次再让用户看见失败
      if (!row.retried) {
        row.retried = true
        window.setTimeout(() => {
          if (!dead && my === token && row.items === null) void fillRow(row, my)
        }, 1500)
        return
      }
      row.error = String(err)
    }
    paintRow(row)
    warmVisible()
  }

  /**
   * 首页各分类横条全铺完（成功失败都算）—— 闪屏在等这个信号，别让它干等到上限。
   * 每条本来就是各拉各的、谁先回来谁先铺，这里只等"最后一条也落定"。
   */
  async function fillRows(my: number): Promise<void> {
    await Promise.all(rows.map((row) => fillRow(row, my))).catch(() => undefined)
    if (my === token) splashReady()
  }

  /** 分类页往后翻页；图源不给总数，就用"这一页空了"当到底 */
  async function loadMore(): Promise<void> {
    if (busy || done || home) return
    const my = token
    busy = true
    paintGrid()
    try {
      const next = await bridgeCall('get_ranking', [current.range, category, page + 1, current.sort])
      if (my !== token) return
      page++
      if (next.length === 0) done = true
      cards.push(...next)
    } catch (err) {
      if (my !== token) return
      if (cards.length === 0) {
        state = 'error'
        errorText = String(err)
        showMessage()
        return
      }
      const hint = document.createElement('span')
      hint.className = 'load-hint'
      hint.textContent = `加载失败：${String(err).replace(/^Error:\s*/, '')}`
      moreEl.textContent = ''
      moreEl.appendChild(hint)
    } finally {
      busy = false
    }
    if (my === token) {
      paintGrid()
      warmVisible()
    }
  }

  function showMessage(): void {
    boardMsgEl.hidden = false
    if (state === 'empty') {
      renderEmpty(boardMsgEl, { icon: '🗂️', title: '这个榜单暂时没数据', hint: '换个日 / 周 / 月或者换个排序试试' })
    } else {
      renderError(boardMsgEl, errorText, retry)
    }
  }

  function retry(): void {
    void load(current.range, current.sort)
  }

  /** 整页挂了、或者首页的 hero 挂了：先自己重来两次（图源冷启动爱抖），两次都还挂才交给用户点 */
  function scheduleRetry(): void {
    if (retries >= 2) return
    retries++
    window.setTimeout(() => {
      const stillBroken = state === 'error' || heroEl.querySelector('.hero-error') !== null
      if (stillBroken) void load(current.range, current.sort)
    }, 1200 * retries)
  }

  async function load(range: RankRange, sort: SortOrder): Promise<void> {
    if (dead) return   // scheduleRetry 的定时器可能在切页之后才醒：别为一张已经拆掉的面板打桥
    current = { range, sort }
    saveState('popular', current)   // 换一次记一次，下次进这一页还是这个榜单
    rangePicker.set(range)
    sortPicker.set(sort)

    const my = ++token
    hero?.destroy()
    hero = null
    state = 'loading'
    errorText = ''
    boardMsgEl.hidden = true
    boardMsgEl.innerHTML = ''
    cards.length = 0
    heroIds = []
    page = 0
    done = false
    busy = false
    gridEl.classList.remove('in')
    for (const row of rows) {
      row.items = null
      row.error = null
      row.armed = false
      row.retried = false
      row.el.classList.remove('in')
    }

    if (!window.pywebview?.api) {
      // 首次启动桥偶尔慢半拍：先把话说清楚，同时盯着它，一就绪自己重来一次，
      // 省得用户自己"切到别的页再切回来"
      heroEl.innerHTML = ''
      state = 'error'
      errorText = 'pywebview api 还没就绪'
      paintPanel()
      showMessage()
      splashReady()
      void waitForApi()
        .then(() => { if (my === token && state === 'error') void load(current.range, current.sort) })
        .catch(() => undefined)
      return
    }

    applyCols()
    renderHeroSkeleton(heroEl)
    paintPanel()
    // 推荐段（rec?.load()）等 hero 落定再开 —— 它要用 hero 那几部的 ID 去重（见下面两处调用）

    try {
      // hero 永远是"当前这一页的分类"最火的三部
      const top = await bridgeCall('get_ranking', [range, category, 1, sort])
      if (my !== token) return
      retries = 0
      hero = top.length === 0 ? null : renderHero(heroEl, top.slice(0, 3), (id) => {
        window.location.hash = `#/album?id=${id}`
      })
      if (top.length === 0) heroEl.innerHTML = ''
      heroIds = top.slice(0, 3).map((item) => item.id)
      rec?.load()            // hero 落定了：推荐段现在知道该避开哪几部
      warmVisible()

      if (top.length === 0) {         // 这一页整块没数据，别留一片空白
        state = 'empty'
        paintPanel()
        showMessage()
        splashReady()
        return
      }
      state = 'ready'
      if (home) {
        paintPanel()
        void fillRows(my)
      } else {
        cards.push(...top.slice(3))   // 前三部在 hero 里，列表从第 4 部接着铺
        done = top.length <= 3        // 第一页就没剩几部，说明这期到底了
        paintPanel()
        warmVisible()
        armReveal(gridEl)             // 整页列表也虚化入场（只在这次加载演一次）
        splashReady()                 // 分类页不是启动路径，但信号照给，别让闪屏干等
      }
    } catch (err) {
      if (my !== token) return
      errorText = String(err)
      if (home) {
        // 首页的 hero 挂了不该连累下面各分类：hero 位置上给个重试，横条照铺
        heroEl.innerHTML = ''
        renderHeroError(heroEl, errorText, () => void load(current.range, current.sort))
        state = 'ready'
        paintPanel()
        rec?.load()          // hero 没出来：没有要避开的 ID，这一段照常铺
        void fillRows(my)
        scheduleRetry()
        return
      }
      // 分类页整页就靠这一次请求，挂了就整页重试（先自动来一次，别一上来就让用户点）
      state = 'error'
      heroEl.innerHTML = ''
      paintPanel()
      showMessage()
      splashReady()
      scheduleRetry()
    }
  }

  /** 面板宽度变了就重算一行几张（首页的骨架和真卡片都跟着换） */
  const resizeObserver = 'ResizeObserver' in window
    ? new ResizeObserver(() => {
        const style = getComputedStyle(panelEl)
        const inner = panelEl.clientWidth
          - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
        const next = colsFor(inner)
        if (next === cols) return
        cols = next
        applyCols()
        if (state === 'loading' || state === 'ready') paintPanel()
      })
    : null
  resizeObserver?.observe(panelEl)

  if (home) {
    // 首页的搜索入口：点一下就进搜索页，按 / 也一样
    el.querySelector<HTMLButtonElement>('.search-entry')!.addEventListener('click', () => {
      window.location.hash = '#/search'
    })
  }

  const onSlash = (event: KeyboardEvent) => {
    if (!home || event.key !== '/') return
    const tag = (event.target as HTMLElement | null)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return
    event.preventDefault()
    window.location.hash = '#/search'
  }
  window.addEventListener('keydown', onSlash)

  const closeMenus = (): void => { rangePicker.close(); sortPicker.close() }
  const onKey = (event: KeyboardEvent) => {
    if (event.key === 'Escape') closeMenus()
  }
  document.addEventListener('click', closeMenus)
  window.addEventListener('keydown', onKey)

  onUnmount(() => {
    dead = true
    hero?.destroy()
    reveal?.disconnect()
    resizeObserver?.disconnect()
    document.removeEventListener('visibilitychange', onVisible)
    window.removeEventListener('focus', recover)
    document.removeEventListener('click', closeMenus)
    window.removeEventListener('keydown', onKey)
    window.removeEventListener('keydown', onSlash)
  })

  // 进来先按上次的选择拉一次（没有记过就是默认的周榜 + 按观看）
  void load(prefs.range, prefs.sort)

  return el
}

/** hero 那一条加载失败：别整页塌掉，就在 hero 位置上给一句话 + 重试 */
function renderHeroError(container: HTMLElement, message: string, retry: () => void): void {
  const box = document.createElement('p')
  box.className = 'hero-error'
  box.textContent = `最火的三部没拉下来：${message.replace(/^Error:\s*/, '')}`
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'hero-error-btn'
  btn.textContent = '重试'
  btn.addEventListener('click', retry)
  box.appendChild(btn)
  container.appendChild(box)
}
