import { renderAlbumList } from '../components/album-list.js'
import { createPicker } from '../components/picker.js'
import { renderAlbumSkeleton, renderError } from '../components/states.js'
import { renderHero, renderHeroSkeleton } from '../components/hero.js'
import type { HeroHandle } from '../components/hero.js'
import { icons, setIcon } from '../components/icons.js'
import { onUnmount } from '../router.js'
import { loadState, pickKey, saveState } from '../store.js'

const RANGES: { key: RankRange; label: string }[] = [
  { key: 'day', label: '日榜' },
  { key: 'week', label: '周榜' },
  { key: 'month', label: '月榜' },
]

const CATEGORIES: { key: ComicCategory; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'doujin', label: '同人' },
  { key: 'single', label: '单本' },
  { key: 'short', label: '短篇' },
  { key: 'hanman', label: '韩漫' },
  { key: 'meiman', label: '美漫' },
]

// 榜单排序：对应后端 get_ranking() 的 order_by
const SORTS: { key: SortOrder; label: string }[] = [
  { key: 'views', label: '按观看' },
  { key: 'likes', label: '按收藏' },
  { key: 'score', label: '按评分' },
  { key: 'images', label: '按图片数' },
  { key: 'comments', label: '按评论' },
  { key: 'latest', label: '按最新' },
]

const RANGE_KEYS = RANGES.map((item) => item.key)
const CATEGORY_KEYS = CATEGORIES.map((item) => item.key)
const SORT_KEYS = SORTS.map((item) => item.key)

interface PopularPrefs {
  range: RankRange
  category: ComicCategory
  sort: SortOrder
}

/** 上次看的榜单 / 分类 / 排序：刷新页面、重开窗口都记得住，认不出的值回退默认 */
function loadPrefs(): PopularPrefs {
  const saved = loadState<Partial<PopularPrefs>>('popular', {})
  return {
    range: pickKey(saved.range, RANGE_KEYS, 'week'),
    category: pickKey(saved.category, CATEGORY_KEYS, 'all'),
    sort: pickKey(saved.sort, SORT_KEYS, 'views'),
  }
}

export function popularPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'popular-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">热门榜单</h1>
    </header>
    <div class="home-search glow-behind">
      <img class="home-avatar" src="/apple-touch-icon.png" alt="" />
      <button type="button" class="search-entry glass">
        <morph-icon class="home-search-ico" size="16" stroke-width="1.8" aria-hidden="true"></morph-icon>
        <span class="search-entry-text">搜作品、作者</span>
        <kbd>/</kbd>
      </button>
    </div>
    <div class="hero"></div>
    <div class="rank-bar">
      <div class="chip-row popular-cats"></div>
      <div class="rank-pickers">
        <div class="range-slot"></div>
        <div class="sort-slot"></div>
      </div>
    </div>
    <h2 class="section-title popular-rest" hidden>其余作品</h2>
    <div class="album-list"></div>
  `

  const heroEl = el.querySelector<HTMLDivElement>('.hero')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const catsEl = el.querySelector<HTMLDivElement>('.popular-cats')!
  const moreEl = el.querySelector<HTMLHeadingElement>('.popular-rest')!
  setIcon(el, '.home-search-ico', icons.search)

  const prefs = loadPrefs()
  let current: PopularPrefs = prefs
  let hero: HeroHandle | null = null

  // 榜单（日 / 周 / 月）和排序是同一个下拉控件：点哪个都按当前条件重拉一次
  const rangePicker = createPicker(RANGES, (key) => { void loadRank(key, current.category, current.sort) })
  const sortPicker = createPicker(SORTS, (key) => { void loadRank(current.range, current.category, key) })
  el.querySelector('.range-slot')!.appendChild(rangePicker.el)
  el.querySelector('.sort-slot')!.appendChild(sortPicker.el)

  /** chips 和两个下拉里的选中态、按钮上的字，都跟着 current 走 */
  function markActive(): void {
    for (const btn of Array.from(catsEl.querySelectorAll('button'))) {
      btn.classList.toggle('active', (btn as HTMLButtonElement).dataset.category === current.category)
    }
    rangePicker.set(current.range)
    sortPicker.set(current.sort)
  }

  /** 点重试就按当前选中的条件再拉一次 */
  function retry(): void {
    void loadRank(current.range, current.category, current.sort)
  }

  async function loadRank(range: RankRange, category: ComicCategory, sort: SortOrder): Promise<void> {
    current = { range, category, sort }
    saveState('popular', current)   // 换一次记一次，下次进首页就直接是这个榜单
    markActive()
    hero?.destroy()
    hero = null
    if (!window.pywebview?.api) {
      heroEl.innerHTML = ''
      moreEl.hidden = true
      renderError(listEl, 'pywebview api 还没就绪', retry)
      return
    }
    try {
      renderHeroSkeleton(heroEl)
      renderAlbumSkeleton(listEl)
      moreEl.hidden = true
      const data = await window.pywebview.api.get_ranking(range, category, 1, sort)
      if (current.range !== range || current.category !== category || current.sort !== sort) return
      if (data.length === 0) {
        heroEl.innerHTML = ''
        renderAlbumList([], listEl, {
          icon: '🗂️',
          title: '这个榜单暂时没数据',
          hint: '换个分类或者日 / 周 / 月试试',
        })
        return
      }
      // 最火的三部单独拎出来做 hero，剩下的接着往下铺
      hero = renderHero(heroEl, data.slice(0, 3), (id) => {
        window.location.hash = `#/album?id=${id}`
      })
      const rest = data.slice(3)
      if (rest.length === 0) {
        moreEl.hidden = true
        listEl.innerHTML = ''
      } else {
        moreEl.hidden = false
        renderAlbumList(rest, listEl)
      }
    } catch (err) {
      if (current.range !== range || current.category !== category || current.sort !== sort) return
      heroEl.innerHTML = ''
      moreEl.hidden = true
      renderError(listEl, String(err), retry)
    }
  }

  // 分类 chips：主维度，铺开来
  for (const cat of CATEGORIES) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.textContent = cat.label
    btn.dataset.category = cat.key
    btn.addEventListener('click', () => {
      void loadRank(current.range, cat.key, current.sort)
    })
    catsEl.appendChild(btn)
  }

  // 首页的搜索入口：点一下就进搜索页，按 / 也一样
  el.querySelector<HTMLButtonElement>('.search-entry')!.addEventListener('click', () => {
    window.location.hash = '#/search'
  })

  const onSlash = (event: KeyboardEvent) => {
    if (event.key !== '/') return
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
    document.removeEventListener('click', closeMenus)
    window.removeEventListener('keydown', onKey)
    window.removeEventListener('keydown', onSlash)
  })

  // 进来先按上次的选择拉一次（没有记过就是默认的周榜 + 全部 + 按观看）
  markActive()
  void loadRank(prefs.range, prefs.category, prefs.sort)

  return el
}
