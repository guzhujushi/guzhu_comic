import { DEFAULT_SETTINGS, loadSettings } from '../settings.js'
import type { AppSettings } from '../settings.js'

/** 设置页的字段表：以后加配置项，加一行就行 */
interface FieldDef {
  path: string          // config.yaml 里的路径，如 window.width
  label: string
  type: 'text' | 'number' | 'bool' | 'pair'
  min?: number
  max?: number
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
    ],
  },
  {
    title: '启动',
    fields: [
      { path: 'dev.url', label: '启动地址', type: 'text', hint: 'Vite 开发服务器地址，或打包后的 dist/index.html', restart: true },
      { path: 'dev.debug', label: '调试模式', type: 'bool', hint: '打开后可以用 F12 / 右键检查', restart: true },
    ],
  },
  {
    title: '阅读器',
    fields: [
      { path: 'reader.restore_progress', label: '自动回到上次那一页', type: 'bool' },
      { path: 'reader.click_to_page', label: '点击左右两侧翻页', type: 'bool', hint: '关掉后只能滚轮 / 方向键翻页' },
    ],
  },
  {
    title: '下载与缓存',
    fields: [
      { path: 'download.workers', label: '图片下载并发数', type: 'number', min: 1, max: 32, hint: '太大容易被图源限速', restart: true },
      { path: 'cache.photo_ttl', label: '章节图列表缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.album_ttl', label: '漫画详情缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.search_ttl', label: '搜索缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
      { path: 'cache.ranking_ttl', label: '榜单缓存（秒）', type: 'number', min: 0, max: 2592000, restart: true },
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
    <h2>设置</h2>
    <p class="settings-note">保存后写进项目根目录的 <code>config.yaml</code>；标了「重启生效」的要重开窗口才用得上。</p>
    <form class="settings-form"></form>
    <p class="cache-usage"></p>
    <div class="settings-actions">
      <button type="button" class="save-btn">保存</button>
      <button type="button" class="reload-btn">重新读取</button>
      <button type="button" class="trim-cache-btn">立即整理缓存</button>
      <button type="button" class="clear-cache-btn">清空缓存</button>
      <span class="settings-status"></span>
    </div>
    <p class="settings-note">缓存（章节图、封面、接口数据）删了会重新下；阅读记录在 data 目录里，清缓存不会碰它。</p>
  `

  const formEl = el.querySelector<HTMLFormElement>('.settings-form')!
  const statusEl = el.querySelector<HTMLElement>('.settings-status')!
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
    fill(await loadSettings(true))
    statusEl.textContent = ''
    void refreshUsage()
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
      try {
        await api()!.save_settings(collect())
        fill(await loadSettings(true))
        statusEl.textContent = '已保存（标「重启生效」的重开窗口后生效）'
      } catch (err) {
        statusEl.textContent = err instanceof Error ? err.message : String(err)
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
      row.appendChild(input)
    }
  } else {
    const input = document.createElement('input')
    input.type = field.type
    input.dataset.path = field.path
    if (field.min !== undefined) input.min = String(field.min)
    if (field.max !== undefined) input.max = String(field.max)
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
