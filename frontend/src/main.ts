import './style.css'
import { registerRoute, startRouter } from './router.js'
import { popularPage } from './pages/popular.js'
import { searchPage } from './pages/search.js'
import { waitForPywebview } from './webstatus.js'
import { albumPage } from './pages/detail.js'
import { readerPage } from './pages/reader.js'

// 注册路由
registerRoute('/popular', popularPage)
registerRoute('/search', searchPage)

// 顶部导航
const nav = document.querySelector<HTMLElement>('#nav')!
nav.innerHTML = `
  <a href="#/popular">热门</a>
  <a href="#/search">搜索</a>
`
registerRoute('/album', albumPage)
registerRoute('/read', readerPage)
startRouter()

// 等 pywebview 就绪（不阻塞页面渲染）
try {
  await waitForPywebview()
  console.log('pywebview 已就绪')
} catch (err) {
  console.error(err)
}
