const app = document.querySelector<HTMLDivElement>('#app')!

app.innerHTML = `
  <div class="container">
    <h1>Guzhu Comic</h1>
    <div class="search-bar">
      <input id="keyword" type="text" placeholder="输入关键词搜索" />
      <button id="search-btn">搜索</button>
    </div>
    <pre id="result"></pre>
  </div>
`

const keywordInput = document.querySelector<HTMLInputElement>('#keyword')!
const searchBtn = document.querySelector<HTMLButtonElement>('#search-btn')!
const resultEl = document.querySelector<HTMLPreElement>('#result')!

async function doSearch(): Promise<void> {
  const keyword = keywordInput.value.trim()
  if (!keyword) {
    resultEl.textContent = '请输入关键词'
    return
  }

  if (!window.pywebview?.api) {
    resultEl.textContent = 'pywebview api 未就绪'
    return
  }

  try {
    resultEl.textContent = '搜索中...'
    const data = await window.pywebview.api.search(keyword)
    resultEl.textContent = JSON.stringify(data, null, 2)
  } catch (err) {
    resultEl.textContent = `搜索失败: ${String(err)}`
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
