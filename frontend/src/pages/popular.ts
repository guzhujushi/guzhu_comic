import { AlbumCard } from '../components/album.js'

const TABS: { key: RankRange; label: string }[] = [
  { key: 'day', label: '日榜' },
  { key: 'week', label: '周榜' },
  { key: 'month', label: '月榜' },
]

export function popularPage(): HTMLElement {
  const el = document.createElement('div')
  el.innerHTML = `
    <h2>热门专辑</h2>
    <div class="popular-tabs"></div>
    <div class="album-list"></div>
  `

  const tabsEl = el.querySelector<HTMLDivElement>('.popular-tabs')!
  const listEl = el.querySelector<HTMLDivElement>('.album-list')!

  let current: RankRange = 'week'

  async function loadRank(range: RankRange): Promise<void> {
    current = range
    tabsEl.querySelectorAll('button').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.range === range)
    })
    if (!window.pywebview?.api) {
      listEl.textContent = 'pywebview api 未就绪'
      return
    }
    try {
      listEl.textContent = '加载中...'
      const data = await window.pywebview.api.get_ranking(range)
      if (current !== range) return
      renderAlbumList(data, listEl)
    } catch (err) {
      if (current !== range) return
      listEl.textContent = `加载失败: ${String(err)}`
    }
  }

  for (const tab of TABS) {
    const btn = document.createElement('button')
    btn.textContent = tab.label
    btn.dataset.range = tab.key
    btn.addEventListener('click', () => {
      void loadRank(tab.key)
    })
    tabsEl.appendChild(btn)
  }

  void loadRank('week')
  return el
}

function renderAlbumList(albums: AlbumSummary[], container: HTMLElement): void {
  container.innerHTML = ''
  for (const item of albums) {
    const card = new AlbumCard()
    card.setData(item)
    container.appendChild(card)
  }
}
