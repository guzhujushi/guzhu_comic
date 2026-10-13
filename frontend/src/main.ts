import './style.css'
import { registerRoute, startRouter } from './router.js'
import { popularPage } from './pages/popular.js'
import { searchPage } from './pages/search.js'
import { waitForPywebview } from './webstatus.js'
import { albumPage } from './pages/detail.js'
import { readerPage } from './pages/reader.js'
import { historyPage } from './pages/history.js'
import { settingsPage } from './pages/settings.js'

// 注册路由
registerRoute('/popular', popularPage)
registerRoute('/search', searchPage)

// 顶部导航：内容列和页面同宽，链接居中
const nav = document.querySelector<HTMLElement>('#nav')!
nav.innerHTML = `
  <div class="nav-inner">
    <a href="#/popular" data-path="/popular">热门</a>
    <a href="#/search" data-path="/search">搜索</a>
    <a href="#/history" data-path="/history">最近阅读</a>
    <a href="#/settings" data-path="/settings">设置</a>
  </div>
`

// 详情页 / 阅读器不从导航进来，就不标高亮，免得跟来路对不上
function syncNav(): void {
  const path = (window.location.hash.slice(1) || '/popular').split('?')[0]
  nav.querySelectorAll<HTMLAnchorElement>('a').forEach((a) => {
    a.classList.toggle('active', a.dataset.path === path)
  })
}
window.addEventListener('hashchange', syncNav)
syncNav()

registerRoute('/album', albumPage)
registerRoute('/read', readerPage)
registerRoute('/history', historyPage)
registerRoute('/settings', settingsPage)

// 先等 pywebview 把 JS 桥注入好再开路由：否则首页会先闪一下"pywebview api 未就绪"
try {
  await waitForPywebview()
  console.log('pywebview 已就绪')
} catch (err) {
  console.error(err)   // 真拿不到也别卡住，路由照跑，页面上会提示未就绪
}
startRouter()