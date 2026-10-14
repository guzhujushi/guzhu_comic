import { DEFAULT_SETTINGS, loadSettings } from '../settings.js'
import { icons, morphIcon, setIcon } from '../components/icons.js'
import type { AppSettings } from '../settings.js'

/** 设置页的字段表：以后加配置项，加一行就行 */
interface FieldDef {
  path: string          // config.yaml 里的路径，如 window.width
  label: string
  type: 'text' | 'number' | 'bool' | 'pair'
  min?: number
  max?: number
  step?: number
  hint?: string
  restart?: boolean     // 改完要重开窗口才生效
}

const GROUPS: { title: string; fields: FieldDef[] }[] = [
  {
    title: '窗口',
    fields: [
      { path: 'window.title', label: '窗口标题', type: 'text', restart: true },
      { path: 'window.width', label: '窗口宽度', type: 'number', min: 400, max: 5000, restart: true },
      { path: 'window.height', label: '窗口高度', type: 'number', min: 400, max: 5000, restart: true },
      { path: 'window.min_size', label: '最小尺寸（宽、高）', type: 'pair', min: 200, max: 5000, restart: true },
      { path: 'window.glass', label: '窗口毛玻璃', type: 'text', hint: 'none / mica / acrylic / tabbed，acrylic 最像毛玻璃；Win11 22H2 起才有效', restart: true },
      { path: 'window.glass_opacity', label: '窗口不透明度', type: 'number', min: 0.35, max: 1, step: 0.01, hint: '1 = 完全不透明；0.9 左右又透又看得清字', restart: true },
    ],
  },
  {
    title: '启动',
    fields: [
      { path: 'dev.use_dev_server', label: '用 vite 开发服务器', type: 'bool', hint: '开发用：连着 vite（5173）改前端不用重打包。打包后的包没有 vite，关着就行 —— 关了是加载包内 dist', restart: true },
      { path: 'dev.url', label: '启动地址', type: 'text', hint: '只在上面那项打开时才会去连它；打包后的包不走这里', restart: true },
      { path: 'dev.debug', label: '调试模式', type: 'bool', hint: '打开后可以用 F12 / 右键检查', restart: true },
      { path: 'server.port', label: '本地服务端口', type: 'number', min: 1024, max: 65535, hint: '页面与图片走同一个端口（同源）：被占就顺着往下退 7 个，还不行就用系统随机端口；但换了端口，主题 / 偏好那一份 localStorage 也跟着换（等于重置）', restart: true },
      { path: 'splash.enabled', label: '开场动画', type: 'bool', hint: '开窗先播「GuZhu」描字动画，放完飞进左上角；动画期间后台把首页那批数据先拉起来，所以揭幕时首页已经铺好了', restart: true },
      { path: 'splash.min_ms', label: '开场动画最短时长（毫秒）', type: 'number', min: 0, max: 10000, hint: '从页面开始加载算起；描字本身 1000ms + 停留 300ms，填得比 1300 小也一样等它写完', restart: true },
      { path: 'splash.max_ms', label: '开场动画最长时长（毫秒）', type: 'number', min: 0, max: 10000, hint: '硬上限：数据再慢也到点就揭幕，露出的骨架后面自己补上', restart: true },
    ],
  },
  {
    title: '阅读器',
    fields: [
      { path: 'reader.restore_progress', label: '自动回到上次那一页', type: 'bool' },
      { path: 'reader.click_to_page', label: '点击左右两侧翻页', type: 'bool', hint: '关掉后只能滚轮 / 方向键翻页' },
      { path: 'reader.mode', label: '阅读模式', type: 'text', hint: 'webtoon = 连续滚动，single = 单页翻页（阅读器里改是立即生效）' },
      { path: 'reader.background', label: '背景色', type: 'text', hint: 'dark / black / gray / light' },
      { path: 'reader.page_gap', label: '页间距（像素）', type: 'number', min: 0, max: 64, hint: '只在连续滚动模式有效' },
      { path: 'reader.width', label: '阅读器图片宽度（像素）', type: 'number', min: 0, max: 2400, hint: '漫画列最多这么宽，0 = 铺满窗口；进阅读器时生效' },
      { path: 'reader.auto_scroll', label: '自动滚屏速度（像素/秒）', type: 'number', min: 0, max: 1000, hint: '0 = 关；只在连续滚动模式有效' },
    ],
  },
  {
    title: '详情页',
    fields: [
      { path: 'detail.chapters_collapse', label: '章节超过几话就折叠', type: 'number', min: 0, max: 500, hint: '0 = 全部展开；折叠后还能一键展开，或直接跳到上次读到的那话' },
      { path: 'detail.comment_preview', label: '右侧评论区先显示几条', type: 'number', min: 0, max: 50, hint: '0 = 不显示评论区；评论只读，不需要登录' },
    ],
  },
  {
    title: '预加载',
    fields: [
      { path: 'prefetch.albums', label: '列表铺完后预热几部的详情', type: 'number', min: 0, max: 30, hint: '列表铺完后，后台一批最多预热这么多部的详情（0 = 关）；列表是分批铺的，铺一批预热点一批；详情里有 tag，留给以后的推荐用', restart: true },
      { path: 'prefetch.chapter_images', label: '预下载图片张数', type: 'number', min: 0, max: 20, hint: '进详情页先下要读那一话的前几张；一话看到「下一话阈值」再下下一话的前几张（0 = 关）', restart: true },
      { path: 'prefetch.next_at', label: '一话看到几成预加载下一话', type: 'number', min: 0, max: 1, step: 0.05, hint: '0.9 = 看到 90%；0 = 关；没有下一话就不会预加载' },
    ],
  },
  {
    title: '推荐',
    fields: [
      { path: 'recommend.limit', label: '一次推荐几张', type: 'number', min: 0, max: 50, hint: '首页第一段与搜索页结果下面那一段各铺几张（0 = 关掉推荐，整段不出现）；推荐只看收藏与搜索记录，不登录、不上传', restart: true },
      { path: 'recommend.candidates', label: '候选池大小（部）', type: 'number', min: 5, max: 200, hint: '从周榜热度前几部里挑这么多部当候选，再用画像打分；调大只影响覆盖度、不影响速度', restart: true },
      { path: 'recommend.hot_weight', label: '热度先验占比', type: 'number', min: 0, max: 1, step: 0.05, hint: '0.3 = 三成看热度、七成看画像匹配；0 = 纯看画像；画像空的时候它就是兜底（热门）', restart: true },
      { path: 'recommend.author_boost', label: '作者命中加成', type: 'number', min: 0, max: 5, step: 0.1, hint: '作者命中相对 tag 命中的倍数，默认 1.5', restart: true },
      { path: 'recommend.half_life_days', label: '画像半衰期（天）', type: 'number', min: 1, max: 365, hint: '收藏 / 搜索的权重每过这么多天减半：30 = 一个月前的一个收藏算半个', restart: true },
    ],
  },
  {
    title: '下载与缓存',
    fields: [
      { path: 'download.workers', label: '图片下载并发数', type: 'number', min: 1, max: 32, hint: '太大容易被图源限速', restart: true },
      { path: 'download.dir', label: '下载目录', type: 'text', hint: '整本下载的离线副本放这儿（用户数据，清缓存不会删）；支持 ~ 与相对路径（相对 ~/.jmreader）', restart: true },
      { path: 'download.retries', label: '单张图重试次数', type: 'number', min: 0, max: 10, hint: '一张图下失败重试几次；还是失败就跳过它，点「继续下载」时再补', restart: true },
      { path: 'download.auto_resume', label: '开窗自动接着下', type: 'bool', hint: '上次没下完的（关窗 / 断电中断的都算），开窗几秒后自动续传，只补缺的部分', restart: true },
      { path: 'cache.photo_ttl', label: '章节图列表缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.album_ttl', label: '漫画详情缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.search_ttl', label: '搜索缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.ranking_ttl', label: '榜单缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.comment_ttl', label: '评论缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.max_size_mb', label: '缓存上限（MB）', type: 'number', min: 0, max: 102400, hint: '2048 就是 2G，0 = 不限；章节图和接口缓存都算在里面', restart: true },
      { path: 'cache.cleanup_interval', label: '定时清理间隔（秒）', type: 'number', min: 30, max: 86400, hint: '后台每隔这么久检查一次，超上限就删最久没看的章节图', restart: true },
    ],
  },
]

function getByPath(obj: unknown, path: string): unknown {
  let cur: any = obj
  for (const key of path.split('.')) {
    if (cur == null) return undefined
    cur = cur[key]
  }
  return cur
}

function setByPath(obj: Record<string, any>, path: string, value: unknown): void {
  const keys = path.split('.')
  const last = keys.pop()!
  let cur: Record<string, any> = obj
  for (const key of keys) {
    if (typeof cur[key] !== 'object' || cur[key] === null) cur[key] = {}
    cur = cur[key]
  }
  cur[last] = value
}

export function settingsPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'settings-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">设置</h1>
      <p class="page-sub">改完点「保存」写回 config.yaml</p>
    </header>
    <p class="settings-note">保存后写进项目根目录的 <code>config.yaml</code>；标了「重启生效」的要重开窗口才用得上。</p>
    <form class="settings-form"></form>
    <p class="cache-usage"></p>
    <div class="settings-actions">
      <button type="button" class="save-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>保存</span></button>
      <button type="button" class="reload-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>重新读取</span></button>
      <button type="button" class="trim-cache-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>立即整理缓存</span></button>
      <button type="button" class="clear-cache-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>清空缓存</span></button>
      <span class="settings-status"></span>
    </div>
    <p class="settings-note">缓存（章节图、封面、接口数据）删了会重新下；阅读记录在 data 目录里，清缓存不会碰它。</p>
    <div class="about-card">
      <img class="about-avatar" src="/apple-touch-icon.png" alt="" />
      <div>
        <p class="about-title">孤竹漫画 Guzhu Comic</p>
        <p class="about-sub">PyWebView + Vite 写的本地漫画阅读器，图源走 JMComic-Crawler-Python；阅读记录和图片都只存在这台机器上。</p>
      </div>
    </div>
  `

  const formEl = el.querySelector<HTMLFormElement>('.settings-form')!
  const statusEl = el.querySelector<HTMLElement>('.settings-status')!
  const saveIco = setIcon(el, '.save-btn morph-icon', icons.save)
  const reloadIco = setIcon(el, '.reload-btn morph-icon', icons.reload)
  setIcon(el, '.trim-cache-btn morph-icon', icons.trim)
  setIcon(el, '.clear-cache-btn morph-icon', icons.cache)
  const usageEl = el.querySelector<HTMLElement>('.cache-usage')!
  const api = () => window.pywebview?.api

  for (const group of GROUPS) {
    const fs = document.createElement('fieldset')
    const legend = document.createElement('legend')
    legend.textContent = group.title
    fs.appendChild(legend)
    for (const field of group.fields) fs.appendChild(buildRow(field))
    formEl.appendChild(fs)
  }

  function fill(settings: AppSettings): void {
    formEl.querySelectorAll<HTMLInputElement>('input[data-path]').forEach((input) => {
      const value = getByPath(settings, input.dataset.path!)
      const index = input.dataset.index
      if (input.type === 'checkbox') input.checked = Boolean(value)
      else if (index !== undefined) input.value = String((value as unknown[] | undefined)?.[Number(index)] ?? '')
      else input.value = value == null ? '' : String(value)
    })
  }

  /** 把表单收成和后端一样的嵌套结构 */
  function collect(): Record<string, any> {
    const payload: Record<string, any> = {}
    formEl.querySelectorAll<HTMLInputElement>('input[data-path]').forEach((input) => {
      const path = input.dataset.path!
      const index = input.dataset.index
      const value: unknown = input.type === 'checkbox'
        ? input.checked
        : input.type === 'number' ? Number(input.value) : input.value
      if (index === undefined) {
        setByPath(payload, path, value)
        return
      }
      const list = (getByPath(payload, path) as unknown[] | undefined) ?? []
      list[Number(index)] = value
      setByPath(payload, path, list)
    })
    return payload
  }

  async function refresh(): Promise<void> {
    if (!api()) {
      statusEl.textContent = 'pywebview api 未就绪'
      return
    }
    reloadIco.classList.add('spin')
    try {
      fill(await loadSettings(true))
      statusEl.textContent = ''
      void refreshUsage()
    } finally {
      reloadIco.classList.remove('spin')
    }
  }

  /** 缓存占用：超上限的话顺手把"立即整理"按钮点亮 */
  async function refreshUsage(): Promise<void> {
    if (!api()?.get_cache_stats) {
      usageEl.textContent = ''
      return
    }
    try {
      const stats = await api()!.get_cache_stats()
      const limit = stats.limit_mb > 0 ? `${stats.limit_mb} MB` : '不限'
      usageEl.textContent = `缓存已用 ${stats.used_mb} MB / 上限 ${limit}（${stats.chapters} 话；每 ${stats.interval} 秒自动整理一次）`
      usageEl.classList.toggle('over', stats.limit_mb > 0 && stats.used_mb > stats.limit_mb)
    } catch (err) {
      usageEl.textContent = '缓存占用读取失败: ' + (err instanceof Error ? err.message : String(err))
    }
  }

  el.querySelector('.save-btn')!.addEventListener('click', () => {
    void (async () => {
      if (!api()) {
        statusEl.textContent = 'pywebview api 未就绪'
        return
      }
      statusEl.textContent = '保存中...'
      morphIcon(saveIco, icons.reload)
      saveIco.classList.add('spin')
      try {
        await api()!.save_settings(collect())
        fill(await loadSettings(true))
        statusEl.textContent = '已保存（标「重启生效」的重开窗口后生效）'
        saveIco.classList.remove('spin')
        morphIcon(saveIco, icons.saved)   // 保存按钮的图标打个勾
      } catch (err) {
        statusEl.textContent = err instanceof Error ? err.message : String(err)
        saveIco.classList.remove('spin')
        morphIcon(saveIco, icons.save)
      }
    })()
  })

  el.querySelector('.reload-btn')!.addEventListener('click', () => { void refresh() })

  el.querySelector('.clear-cache-btn')!.addEventListener('click', () => {
    void (async () => {
      if (!api()) {
        statusEl.textContent = 'pywebview api 未就绪'
        return
      }
      statusEl.textContent = '清理中...'
      try {
        const res = await api()!.clear_cache()
        statusEl.textContent = `缓存已清空：接口数据 ${res.meta_rows} 条、文件 ${res.cache_files} 个（阅读记录没动）`
        void refreshUsage()
      } catch (err) {
        statusEl.textContent = err instanceof Error ? err.message : String(err)
      }
    })()
  })

  el.querySelector('.trim-cache-btn')!.addEventListener('click', () => {
    void (async () => {
      if (!api()?.cleanup_cache) {
        statusEl.textContent = 'pywebview api 未就绪'
        return
      }
      statusEl.textContent = '整理中...'
      try {
        const res = await api()!.cleanup_cache()
        statusEl.textContent = res.removed_chapters
          ? `已清理 ${res.removed_chapters} 话，释放 ${res.freed_mb} MB，现用 ${res.used_mb} MB`
          : `没有超上限，不用清理（现用 ${res.used_mb} MB）`
        void refreshUsage()
      } catch (err) {
        statusEl.textContent = err instanceof Error ? err.message : String(err)
      }
    })()
  })

  fill(DEFAULT_SETTINGS)   // 先用默认值把表单铺出来，免得空着
  void refresh()

  return el
}

function buildRow(field: FieldDef): HTMLElement {
  const row = document.createElement('div')
  row.className = 'settings-row'

  const label = document.createElement('label')
  label.textContent = field.label
  row.appendChild(label)

  if (field.type === 'bool') {
    const input = document.createElement('input')
    input.type = 'checkbox'
    input.dataset.path = field.path
    row.appendChild(input)
  } else if (field.type === 'pair') {
    for (const index of [0, 1]) {
      const input = document.createElement('input')
      input.type = 'number'
      input.dataset.path = field.path
      input.dataset.index = String(index)
      if (field.min !== undefined) input.min = String(field.min)
      if (field.max !== undefined) input.max = String(field.max)
      if (field.step !== undefined) input.step = String(field.step)
      row.appendChild(input)
    }
  } else {
    const input = document.createElement('input')
    input.type = field.type
    input.dataset.path = field.path
    if (field.min !== undefined) input.min = String(field.min)
    if (field.max !== undefined) input.max = String(field.max)
    if (field.step !== undefined) input.step = String(field.step)
    row.appendChild(input)
  }

  if (field.hint) {
    const hint = document.createElement('span')
    hint.className = 'field-hint'
    hint.textContent = field.hint
    row.appendChild(hint)
  }
  if (field.restart) {
    const tag = document.createElement('span')
    tag.className = 'restart-tag'
    tag.textContent = '重启生效'
    row.appendChild(tag)
  }
  return row
}
