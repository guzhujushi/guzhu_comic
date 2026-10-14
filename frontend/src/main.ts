import './style.css'
import { registerRoute, startRouter } from './router.js'
import { popularPage } from './pages/popular.js'
import { searchPage } from './pages/search.js'
import { waitForBridge } from './webstatus.js'
import { DEFAULT_SETTINGS, loadSettings } from './settings.js'
import type { AppSettings } from './settings.js'
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
import { aboutPage } from './pages/about.js'
import { createResume } from './resume.js'
import { createIcon, icons } from './components/icons.js'
import { morphIcon } from './components/icons.js'
import { currentTheme, setTheme } from './theme.js'

// 注册路由
registerRoute('/popular', popularPage)
registerRoute('/search', searchPage)

// 左侧导航栏：品牌 + 链接；当前页的图标会变个形
type NavItem = { path: string; label: string; icon: typeof icons.popular; activeIcon: typeof icons.popular }

const NAV_ITEMS: NavItem[] = [
  { path: '/popular', label: '热门', icon: icons.popular, activeIcon: icons.popularOn },
  { path: '/search', label: '搜索', icon: icons.search, activeIcon: icons.searchDone },
  { path: '/forum', label: '论坛', icon: icons.forum, activeIcon: icons.forumOn },
  { path: '/history', label: '最近阅读', icon: icons.history, activeIcon: icons.historyOn },
  { path: '/favorites', label: '收藏', icon: icons.heart, activeIcon: icons.heartOn },
  { path: '/downloads', label: '我的下载', icon: icons.download, activeIcon: icons.downloadOn },
]

// 贴左下角那两个：关于与设置并排，主题开关在它们下面。
// 它们不是"逛内容"的入口，跟上面那排分开——上面那排是内容导航，这排是应用级的。
const NAV_FOOT_ITEMS: NavItem[] = [
  { path: '/about', label: '关于', icon: icons.about, activeIcon: icons.aboutOn },
  { path: '/settings', label: '设置', icon: icons.settings, activeIcon: icons.settingsOn },
]

const nav = document.querySelector<HTMLElement>('#nav')!
nav.innerHTML = `
  <div class="nav-brand">
    <img class="brand-avatar" src="/apple-touch-icon.png" alt="" />
    <div class="brand-text">
      <!-- 品牌行 = 字标 + 「漫画」：开场那枚 GuZhu 字标只取代「孤竹」两字（用户 2026-10-14 定的落位）。
           .brand-slot 就是字标的落点，里面那句「孤竹」是兜底文案 —— 老 index.html 没有那份闪屏 SVG 时照旧显示。 -->
      <span class="brand-mark"><span class="brand-slot">孤竹</span>漫画</span>
      <span class="brand-sub">Guzhu Comic</span>
    </div>
  </div>
  <nav class="nav-links"></nav>
  <div class="nav-foot">
    <div class="nav-foot-row"></div>
  </div>
`
// 开场闪屏（写死在 index.html 里那块）交给它接管，顺手把导航里的字标落点放好。
// 得等导航铺完再调 —— 落点先存在，字标才知道往哪飞。
bootSplash()

const navInner = nav.querySelector<HTMLElement>('.nav-links')!
const navFootRow = nav.querySelector<HTMLElement>('.nav-foot-row')!
const navIcons = new Map<string, HTMLElement>()
const navLinks = new Map<string, HTMLAnchorElement>()

function addNavLink(item: NavItem, parent: HTMLElement): void {
  const a = document.createElement('a')
  a.href = `#${item.path}`
  a.dataset.path = item.path
  const ico = createIcon(item.icon, { size: 16 })
  const text = document.createElement('span')
  text.textContent = item.label
  a.append(ico, text)
  navIcons.set(item.path, ico)
  navLinks.set(item.path, a)
  parent.appendChild(a)
}

for (const item of NAV_ITEMS) addNavLink(item, navInner)
for (const item of NAV_FOOT_ITEMS) addNavLink(item, navFootRow)

// 主题开关：贴在导航栏底部。换的那一下走 View Transitions —— 从点击处摊开一个圆，
// 把新配色揭出来（motion.ts）。桌面上阅读器里没有导航，所以阅读器设置面板里也有一份。
const themeBtn = document.createElement('button')
themeBtn.type = 'button'
themeBtn.className = 'nav-theme'
const themeIcon = createIcon(icons.themeDark, { size: 16 })
const themeLabel = document.createElement('span')
themeBtn.append(themeIcon, themeLabel)
const navFoot = nav.querySelector<HTMLElement>('.nav-foot')!
navFoot.appendChild(themeBtn)

// 「继续阅读」摆在这一摞的最上面（卡片 + 按钮）：它牵着「最近阅读」里时间最近的那一条，
// 点一下接着上次那页看。没读过就整块藏起来，不留空位。
const resume = createResume()
navFoot.prepend(resume.el)

function paintThemeButton(): void {
  const dark = currentTheme() === 'dark'
  morphIcon(themeIcon, dark ? icons.themeDark : icons.themeLight)
  themeLabel.textContent = dark ? '深色' : '浅色'
  // 导航栏窄成 64px 时这个标签会被 CSS 藏掉，只剩图标 —— 悬停提示得自己带上
  themeBtn.title = dark ? '切到浅色' : '切到深色'
}
themeBtn.addEventListener('click', (event) => {
  void setTheme(event, currentTheme() === 'dark' ? 'light' : 'dark').then(paintThemeButton)
})
paintThemeButton()

// 详情页 / 阅读器不从导航进来，就不标高亮，免得跟来路对不上
function syncNav(): void {
  const path = (window.location.hash.slice(1) || '/popular').split('?')[0]
  for (const item of [...NAV_ITEMS, ...NAV_FOOT_ITEMS]) {
    const a = navLinks.get(item.path)!
    const on = item.path === path
    a.classList.toggle('active', on)
    morphIcon(navIcons.get(item.path)!, on ? item.activeIcon : item.icon)
  }
}
window.addEventListener('hashchange', syncNav)
// 换页就刷一次「继续阅读」。再补一次 500ms 后的：阅读器退出时先发 `save_progress`
// 再改 hash，两条桥调用在 Python 侧是两个线程，偶尔会抢在写库前读到旧页码 ——
// 这张卡写着"读到第几页"，差一页一眼就看得出来（本地 sqlite 一条 20 行的查询，不心疼）。
let resumeSettle = 0
window.addEventListener('hashchange', () => {
  void resume.refresh()
  window.clearTimeout(resumeSettle)
  resumeSettle = window.setTimeout(() => void resume.refresh(), 500)
})
syncNav()

registerRoute('/album', albumPage)
registerRoute('/read', readerPage)
registerRoute('/history', historyPage)
registerRoute('/favorites', favoritesPage)
registerRoute('/downloads', downloadsPage)
registerRoute('/category', categoryPage)
registerRoute('/forum', forumPage)
registerRoute('/settings', settingsPage)
registerRoute('/about', aboutPage)

// 先等 pywebview 把 JS 桥**挂好方法**再开路由（两步注入，见 webstatus.ts）：
// 光等"api 对象在"就开路由的话，首页第一次铺的时候方法还没挂上 —— 页面自己会重试所以看着
// 没事，但「推荐段」这张一次性的卡会以为自己不该出现，永久藏掉，只能切页回来才看得见。
// 而且启动那一下它会注**两遍**（第二遍把正在飞的调用的回调清掉 → promise 永不 settle），
// 所以 waitForBridge() 还要等最后一次注入安静下来才放行 —— 不然卡在这句上的就是整个启动。
try {
  const api = await waitForBridge()
  console.log('pywebview 已就绪')
  // 向后端报到：热更新那份前端"起没起来"就靠这一声（30 秒没报到 = 下次开窗自动撤掉它并退回
  // 上一版，见 backend/updater.py）。别删 —— 删了以后更新出问题就得手动去删 ~/.jmreader/web。
  void api.notify_booted?.().catch(() => undefined)
  // 闪屏还在放：趁这会儿把首页那批元数据先拉起来（hero + 各分类 + 推荐段），
  // 等路由铺首页时那些请求就全是缓存命中（实测毫秒级）。榜单条件要跟 board 自己那份一致，
  // 所以问它要 —— 自己再读一遍 localStorage 早晚会读岔，预热的是另一把 cache key 就白拉了。
  const prefs = homePrefs()
  void api.prefetch_home(prefs.range, prefs.sort).catch(() => undefined)
  // 桥就绪才拉得动「继续阅读」那张卡（它要读 data/app.db 的 history 表）
  void resume.refresh()
} catch (err) {
  console.error(err)   // 真拿不到也别卡住，路由照跑，页面上会提示未就绪
}
// 窗口开着毛玻璃的话（config.yaml 的 window.glass），页面自己也留点透明度，
// DWM 在窗口后面画的那层模糊才透得上来
// 这一段在 startRouter() 前面，抛出去就是整窗空白。loadSettings 内部已经 catch 了读配置的失败，
// 正常不会抛 —— 但这是"开路由之前的最后一道闸"，用几行把它焊死，别让任何意外卡在这儿。
let boot: AppSettings = DEFAULT_SETTINGS
try {
  boot = await loadSettings()
} catch (err) {
  console.error('读配置失败，用默认值启动', err)
}
document.documentElement.dataset.glass = boot.window.glass === 'none' ? 'off' : 'on'
splashConfigure(boot.splash)   // 配置到手才作数：关了就当场撤，时长按配置重排

startRouter()
// 开窗自动查一次更新（config.yaml 的 update.auto）：有新版只在右下角提一句，装不装由用户点。
// 排在闪屏之后：启动那几秒的每一帧都留给首屏，别跟它抢。
if (boot.update.enabled && boot.update.auto) {
  window.setTimeout(() => void hintUpdate(), 2600)
}

/** 查一次更新，有新版就挂个提示条；查不成（离线 / 还没发布）安静地不出现 */
async function hintUpdate(): Promise<void> {
  const api = window.pywebview?.api
  if (!api?.check_update || !api.apply_update) return
  try {
    const info = await api.check_update()
    // known_bad = 上一版装上去没能开起来（已自动退回），别再劝人装一遍；
    // too_new = 那版要更高的安装包，页面上劝不动，只能去下新安装包
    if (info.error || !info.available || info.too_new || info.known_bad) return
    showUpdateHint(info)
  } catch {
    /* 查更新从来不该影响开窗 */
  }
}

/** 右下角那条「有新版前端」：更新说明挂在悬停标题上，摘要在右下角放不下 */
function showUpdateHint(info: UpdateInfo): void {
  const box = document.createElement('div')
  box.className = 'update-hint'

  const text = document.createElement('span')
  text.className = 'update-hint-text'
  text.textContent = `有新版前端 ${info.version}`
  if (info.notes) text.title = info.notes

  const go = document.createElement('button')
  go.type = 'button'
  go.className = 'update-hint-go'
  go.textContent = '更新'

  const close = document.createElement('button')
  close.type = 'button'
  close.className = 'update-hint-x'
  close.setAttribute('aria-label', '这次先不更新')
  close.append(createIcon(icons.close, { size: 13 }))

  go.addEventListener('click', () => {
    void (async () => {
      go.disabled = true
      text.textContent = '正在下载…'
      try {
        const res = await window.pywebview!.api.apply_update()
        // 静态服务每请求重挑根，所以装完只要刷新页面就是新的那份
        text.textContent = res.changed ? '装好了，正在刷新页面…' : '本来就没有新版'
        if (res.changed) window.setTimeout(() => window.location.reload(), 600)
      } catch (err) {
        go.disabled = false
        text.textContent = `更新失败：${String(err).replace(/^Error:\s*/, '')}`
      }
    })()
  })
  close.addEventListener('click', () => box.remove())

  box.append(text, go, close)
  document.body.appendChild(box)
}
