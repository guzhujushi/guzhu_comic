import { renderAlbumList } from '../components/album-list.js';
import { renderAlbumSkeleton, renderError } from '../components/states.js';

const TABS: { key: RankRange; label: string }[] = [
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
      <p class="page-sub">挑分类，再挑日 / 周 / 月</p>
    </header>
    <div class="chip-row popular-cats"></div>
    <div class="tab-row popular-tabs"></div>
    <div class="album-list"></div>
  `

  const tabsEl = el.querySelector<HTMLDivElement>('.popular-tabs')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const catsEl = el.querySelector<HTMLDivElement>('.popular-cats')!

  let current = { range: 'week' as RankRange, category: 'all' as ComicCategory };

  // 两个按钮行都标一下选中，别只有日/周/月有高亮
  function markActive(): void {
    for (const btn of Array.from(tabsEl.querySelectorAll('button'))) {
      btn.classList.toggle('active', (btn as HTMLButtonElement).dataset.range === current.range)
    }
    for (const btn of Array.from(catsEl.querySelectorAll('button'))) {
      btn.classList.toggle('active', (btn as HTMLButtonElement).dataset.category === current.category)
    }
  }

  /** 点重试就按当前选中的条件再拉一次 */
  function retry(): void {
    void loadRank(current.range, current.category)
  }

  async function loadRank(range: RankRange, category: ComicCategory): Promise<void> {
    current = { range, category };
    markActive()
    if (!window.pywebview?.api) {
      renderError(listEl, 'pywebview api 还没就绪', retry)
      return
    }
    try {
      // 先铺骨架，别让列表区域空着等
      renderAlbumSkeleton(listEl)
      const data = await window.pywebview.api.get_ranking(range, category)
      if (current.range !== range || current.category !== category) return
      renderAlbumList(data, listEl, {
        icon: '🗂️',
        title: '这个榜单暂时没数据',
        hint: '换个分类或者日 / 周 / 月试试',
      })
    } catch (err) {
      if (current.range !== range || current.category !== category) return
      renderError(listEl, String(err), retry)
    }
  }

  // 分类 chips（主要维度）
  for (const cat of CATEGORIES) {
    const btn = document.createElement('button')
    btn.textContent = cat.label
    btn.dataset.category = cat.key
    btn.addEventListener('click', () => {
      void loadRank(current.range, cat.key)
    })
    catsEl.appendChild(btn)
  }

  // 日/周/月 tabs
  for (const tab of TABS) {
    const btn = document.createElement('button')
    btn.textContent = tab.label
    btn.dataset.range = tab.key
    btn.addEventListener('click', () => {
      void loadRank(tab.key, current.category)
    })
    tabsEl.appendChild(btn)
  }

  void loadRank('week', 'all')

  return el
}