import './style.css'
import { registerRoute, startRouter } from './router.js'
import { popularPage } from './pages/popular.js'
import { searchPage } from './pages/search.js'
import { waitForPywebview } from './webstatus.js'
import { loadSettings } from './settings.js'
import { bootSplash, splashConfigure } from './splash.js'
import { homePrefs } from './pages/board.js'
import { albumPage } from './pages/detail.js'
import { readerPage } from './pages/reader.js'
import { historyPage } from './pages/history.js'
import { favoritesPage } from './pages/favorites.js'
import { downloadsPage } from './pages/downloads.js'
import { categoryPage } from './pages/category.js'
import { forumPage } from './pages/forum.js'
import { settingsPage } from './pages/settings.js'
import { createIcon, icons } from './components/icons.js'
import { morphIcon } from './components/icons.js'

// 注册路由
registerRoute('/popular', popularPage)
registerRoute('/search', searchPage)

// 左侧导航栏：品牌 + 链接；当前页的图标会变个形
const NAV_ITEMS = [
  { path: '/popular', label: '热门', icon: icons.popular, activeIcon: icons.popularOn },
  { path: '/search', label: '搜索', icon: icons.search, activeIcon: icons.searchDone },
  { path: '/forum', label: '论坛', icon: icons.forum, activeIcon: icons.forumOn },
  { path: '/history', label: '最近阅读', icon: icons.history, activeIcon: icons.historyOn },
  { path: '/favorites', label: '收藏', icon: icons.heart, activeIcon: icons.heartOn },
  { path: '/downloads', label: '我的下载', icon: icons.download, activeIcon: icons.downloadOn },
  { path: '/settings', label: '设置', icon: icons.settings, activeIcon: icons.settingsOn },
]

const nav = document.querySelector<HTMLElement>('#nav')!
nav.innerHTML = `
  <div class="nav-brand">
    <img class="brand-avatar" src="/apple-touch-icon.png" alt="" />
    <div class="brand-text">
      <span class="brand-mark">孤竹漫画</span>
      <span class="brand-sub">Guzhu Comic</span>
    </div>
  </div>
  <nav class="nav-links"></nav>
`
// 开场闪屏（写死在 index.html 里那块）交给它接管，顺手把导航里的字标落点放好。
// 得等导航铺完再调 —— 落点先存在，字标才知道往哪飞。
bootSplash()

const navInner = nav.querySelector<HTMLElement>('.nav-links')!
const navIcons = new Map<string, HTMLElement>()

for (const item of NAV_ITEMS) {
  const a = document.createElement('a')
  a.href = `#${item.path}`
  a.dataset.path = item.path
  const ico = createIcon(item.icon, { size: 16 })
  const text = document.createElement('span')
  text.textContent = item.label
  a.append(ico, text)
  navIcons.set(item.path, ico)
  navInner.appendChild(a)
}

// 详情页 / 阅读器不从导航进来，就不标高亮，免得跟来路对不上
function syncNav(): void {
  const path = (window.location.hash.slice(1) || '/popular').split('?')[0]
  for (const item of NAV_ITEMS) {
    const a = navInner.querySelector<HTMLAnchorElement>(`a[data-path="${item.path}"]`)!
    const on = a.dataset.path === path
    a.classList.toggle('active', on)
    morphIcon(navIcons.get(item.path)!, on ? item.activeIcon : item.icon)
  }
}
window.addEventListener('hashchange', syncNav)
syncNav()

registerRoute('/album', albumPage)
registerRoute('/read', readerPage)
registerRoute('/history', historyPage)
registerRoute('/favorites', favoritesPage)
registerRoute('/downloads', downloadsPage)
registerRoute('/category', categoryPage)
registerRoute('/forum', forumPage)
registerRoute('/settings', settingsPage)

// 先等 pywebview 把 JS 桥注入好再开路由：否则首页会先闪一下"pywebview api 未就绪"
try {
  const api = await waitForPywebview()
  console.log('pywebview 已就绪')
  // 闪屏还在放：趁这会儿把首页那批元数据先拉起来（hero + 各分类 + 推荐段），
  // 等路由铺首页时那些请求就全是缓存命中（实测毫秒级）。榜单条件要跟 board 自己那份一致，
  // 所以问它要 —— 自己再读一遍 localStorage 早晚会读岔，预热的是另一把 cache key 就白拉了。
  const prefs = homePrefs()
  void api.prefetch_home(prefs.range, prefs.sort).catch(() => undefined)
} catch (err) {
  console.error(err)   // 真拿不到也别卡住，路由照跑，页面上会提示未就绪
}
// 窗口开着毛玻璃的话（config.yaml 的 window.glass），页面自己也留点透明度，
// DWM 在窗口后面画的那层模糊才透得上来
const boot = await loadSettings()
document.documentElement.dataset.glass = boot.window.glass === 'none' ? 'off' : 'on'
splashConfigure(boot.splash)   // 配置到手才作数：关了就当场撤，时长按配置重排

startRouter()