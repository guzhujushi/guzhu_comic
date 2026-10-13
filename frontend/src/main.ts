import './style.css'
import { AlbumCard } from './components/album.js'

const app = document.querySelector<HTMLDivElement>('#app')!

app.innerHTML = `
  <div class="container">
    <h1>Guzhu Comic</h1>
    <div class="search-bar">
      <input id="keyword" type="text" placeholder="输入关键词搜索" />
      <button id="search-btn">搜索</button>
    </div>
    <div id="album-list"></div>
  </div>
`

const keywordInput = document.querySelector<HTMLInputElement>('#keyword')!
const searchBtn = document.querySelector<HTMLButtonElement>('#search-btn')!
const albumListEl = document.querySelector<HTMLPreElement>('#album-list')!

function renderAlbumList(albums: AlbumSummary[], container: HTMLElement) {
  container.innerHTML = ''

  for (const item of albums) {
    const card = new AlbumCard()
    card.setData(item)
    container.appendChild(card)
  }
}

async function doSearch(): Promise<void> {
  const keyword = keywordInput.value.trim()
  if (!keyword) {
    albumListEl.textContent = '请输入关键词'
    return
  }

  if (!window.pywebview?.api) {
    albumListEl.textContent = 'pywebview api 未就绪'
    return
  }

  try {
    albumListEl.textContent = '搜索中...'
    const data = await window.pywebview.api.search(keyword)
    renderAlbumList(data, albumListEl)
  } catch (err) {
    albumListEl.textContent = `搜索失败: ${String(err)}`
  }
}

searchBtn.addEventListener('click', () => {
  void doSearch()
})

keywordInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    void doSearch()
  }
})
