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

// 先等 pywebview 把 JS 桥注入好再开路由：否则首页会先闪一下"pywebview api 未就绪"
try {
  await waitForPywebview()
  console.log('pywebview 已就绪')
} catch (err) {
  console.error(err)   // 真拿不到也别卡住，路由照跑，页面上会提示未就绪
}
startRouter()
