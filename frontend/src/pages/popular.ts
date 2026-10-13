import { renderAlbumList } from '../components/album-list.js';
import { renderAlbumSkeleton, renderError } from '../components/states.js';
import { renderHero, renderHeroSkeleton } from '../components/hero.js';
import type { HeroHandle } from '../components/hero.js';
import { icons, morphIcon, setIcon } from '../components/icons.js';
import { onUnmount } from '../router.js';

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
];

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
      <div class="rank-picker">
        <button type="button" class="rank-btn" aria-haspopup="true" aria-expanded="false">
          <span class="rank-label"></span>
          <morph-icon class="rank-caret" size="14" stroke-width="1.8" aria-hidden="true"></morph-icon>
        </button>
        <div class="rank-menu" hidden></div>
      </div>
    </div>
    <h2 class="section-title popular-rest" hidden>其余作品</h2>
    <div class="album-list"></div>
  `

  const heroEl = el.querySelector<HTMLDivElement>('.hero')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const catsEl = el.querySelector<HTMLDivElement>('.popular-cats')!
  const moreEl = el.querySelector<HTMLHeadingElement>('.popular-rest')!
  const pickerBtn = el.querySelector<HTMLButtonElement>('.rank-btn')!
  const menuEl = el.querySelector<HTMLDivElement>('.rank-menu')!
  const labelEl = el.querySelector<HTMLSpanElement>('.rank-label')!
  const caret = setIcon(el, '.rank-caret', icons.down)
  setIcon(el, '.home-search-ico', icons.search)

  let current = { range: 'week' as RankRange, category: 'all' as ComicCategory }
  let hero: HeroHandle | null = null

  function openMenu(open: boolean): void {
    menuEl.hidden = !open
    pickerBtn.setAttribute('aria-expanded', String(open))
    morphIcon(caret, open ? icons.up : icons.down)
  }

  /** chips 和下拉里的选中态、按钮上的字，都跟着 current 走 */
  function markActive(): void {
    for (const btn of Array.from(catsEl.querySelectorAll('button'))) {
      btn.classList.toggle('active', (btn as HTMLButtonElement).dataset.category === current.category)
    }
    for (const btn of Array.from(menuEl.querySelectorAll('button'))) {
      btn.classList.toggle('active', (btn as HTMLButtonElement).dataset.range === current.range)
    }
    labelEl.textContent = RANGES.find((range) => range.key === current.range)?.label ?? ''
  }

  /** 点重试就按当前选中的条件再拉一次 */
  function retry(): void {
    void loadRank(current.range, current.category)
  }

  async function loadRank(range: RankRange, category: ComicCategory): Promise<void> {
    current = { range, category }
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
      const data = await window.pywebview.api.get_ranking(range, category)
      if (current.range !== range || current.category !== category) return
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
      if (current.range !== range || current.category !== category) return
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
      void loadRank(current.range, cat.key)
    })
    catsEl.appendChild(btn)
  }

  // 榜单：收进下拉，别跟分类抢级别
  for (const range of RANGES) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.textContent = range.label
    btn.dataset.range = range.key
    btn.addEventListener('click', () => {
      openMenu(false)
      void loadRank(range.key, current.category)
    })
    menuEl.appendChild(btn)
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

  pickerBtn.addEventListener('click', (event) => {
    event.stopPropagation()
    openMenu(menuEl.hasAttribute('hidden'))
  })

  const closeMenu = () => openMenu(false)
  const onKey = (event: KeyboardEvent) => {
    if (event.key === 'Escape') openMenu(false)
  }
  document.addEventListener('click', closeMenu)
  window.addEventListener('keydown', onKey)

  onUnmount(() => {
    hero?.destroy()
    document.removeEventListener('click', closeMenu)
    window.removeEventListener('keydown', onKey)
    window.removeEventListener('keydown', onSlash)
  })

  void loadRank('week', 'all')

  return el
}