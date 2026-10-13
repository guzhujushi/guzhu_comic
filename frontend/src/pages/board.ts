// pages/board.ts
// 热门榜单：hero（当前分类最火三部）+ 分类标签条 + 面板，
// 「#/popular」是全部那一页，「#/category?c=xx」是某个分类那一页，两边共用这一套。
import { renderAlbumList } from '../components/album-list.js'
import { createIcon, icons, setIcon } from '../components/icons.js'
import { createPicker } from '../components/picker.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { renderHero, renderHeroSkeleton } from '../components/hero.js'
import type { HeroHandle } from '../components/hero.js'
import { onUnmount } from '../router.js'
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

interface BoardPrefs {
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
      rows.push({ key, el: section, rowEl: row, items: null, error: null, armed: false })
    }
  } else {
    gridEl.className = 'album-list reveal'
    panelEl.append(gridEl, moreEl)
  }

  const prefs = loadPrefs()
  let current: BoardPrefs = prefs
  let hero: HeroHandle | null = null
  let token = 0                 // 每换一次条件加一，晚回来的旧结果直接丢
  let cols = 5
  let state: 'loading' | 'ready' | 'empty' | 'error' = 'loading'
  let errorText = ''

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
    if (reveal) reveal.observe(target)
    else target.classList.add('in')
  }

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

  /** 一个分类的请求：首页各拉各的，谁先回来谁先铺，不互相等 */
  async function fillRow(row: CatRow, my: number): Promise<void> {
    const api = window.pywebview?.api
    if (!api) return
    try {
      const items = await api.get_ranking(current.range, row.key, 1, current.sort)
      if (my !== token) return
      row.items = items
    } catch (err) {
      if (my !== token) return
      row.error = String(err)
    }
    paintRow(row)
  }

  /** 分类页往后翻页；图源不给总数，就用"这一页空了"当到底 */
  async function loadMore(): Promise<void> {
    if (busy || done || home) return
    const api = window.pywebview?.api
    if (!api) return
    const my = token
    busy = true
    paintGrid()
    try {
      const next = await api.get_ranking(current.range, category, page + 1, current.sort)
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
    if (my === token) paintGrid()
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

  async function load(range: RankRange, sort: SortOrder): Promise<void> {
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
    page = 0
    done = false
    busy = false
    gridEl.classList.remove('in')
    for (const row of rows) {
      row.items = null
      row.error = null
      row.armed = false
      row.el.classList.remove('in')
    }

    if (!window.pywebview?.api) {
      heroEl.innerHTML = ''
      state = 'error'
      errorText = 'pywebview api 还没就绪'
      paintPanel()
      showMessage()
      return
    }

    applyCols()
    renderHeroSkeleton(heroEl)
    paintPanel()

    try {
      // hero 永远是"当前这一页的分类"最火的三部
      const top = await window.pywebview.api.get_ranking(range, category, 1, sort)
      if (my !== token) return
      hero = top.length === 0 ? null : renderHero(heroEl, top.slice(0, 3), (id) => {
        window.location.hash = `#/album?id=${id}`
      })
      if (top.length === 0) heroEl.innerHTML = ''

      if (top.length === 0) {         // 这一页整块没数据，别留一片空白
        state = 'empty'
        paintPanel()
        showMessage()
        return
      }
      state = 'ready'
      if (home) {
        paintPanel()
        for (const row of rows) void fillRow(row, my)
      } else {
        cards.push(...top.slice(3))   // 前三部在 hero 里，列表从第 4 部接着铺
        done = top.length <= 3        // 第一页就没剩几部，说明这期到底了
        paintPanel()
        armReveal(gridEl)             // 整页列表也虚化入场（只在这次加载演一次）
      }
    } catch (err) {
      if (my !== token) return
      state = 'error'
      errorText = String(err)
      heroEl.innerHTML = ''
      paintPanel()
      showMessage()
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
    hero?.destroy()
    reveal?.disconnect()
    resizeObserver?.disconnect()
    document.removeEventListener('click', closeMenus)
    window.removeEventListener('keydown', onKey)
    window.removeEventListener('keydown', onSlash)
  })

  // 进来先按上次的选择拉一次（没有记过就是默认的周榜 + 按观看）
  void load(prefs.range, prefs.sort)

  return el
}
