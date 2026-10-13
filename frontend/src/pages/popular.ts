import { AlbumCard } from '../components/album.js'

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
  el.innerHTML = `
    <h2>热门专辑</h2>
    <div class="popular-cats"></div>
    <div class="popular-tabs"></div>
    <div class="album-list"></div>
  `

  const tabsEl = el.querySelector<HTMLDivElement>('.popular-tabs')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const catsEl = el.querySelector<HTMLDivElement>('.popular-cats')!

  let current = { range: 'week' as RankRange, category: 'all' as ComicCategory };

  async function loadRank(range: RankRange, category: ComicCategory): Promise<void> {
    current = { range, category };
    tabsEl.querySelectorAll('button').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.range === range)
    })
    if (!window.pywebview?.api) {
      listEl.textContent = 'pywebview api 未就绪'
      return
    }
    try {
      listEl.textContent = '加载中...'
      const data = await window.pywebview.api.get_ranking(range, category)
      if (current.range !== range || current.category !== category) return
      renderAlbumList(data, listEl)
    } catch (err) {
      if (current.range !== range || current.category !== category) return
      listEl.textContent = `加载失败: ${String(err)}`
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

// 日/周/月 tabs（保留）
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

function renderAlbumList(albums: AlbumSummary[], container: HTMLElement): void {
  container.innerHTML = ''
  for (const item of albums) {
    const card = new AlbumCard()
    card.setData(item)
    container.appendChild(card)
  }
}
return el
}