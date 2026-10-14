// pages/settings.ts
// 设置页。**字段表是后端给的**（`backend/settings_spec.py` 那张表，走 get_settings_spec）：
// 加一个配置项只要后端加一行，这儿的表单自己就长出来了 —— 不会出现"后端加了键、前端没这个框"。
// 这儿只负责：按 kind 造控件、收值、保存，外加几块不是配置的东西（更新 / 磁盘 / 数据 / 日志）。
import { DEFAULT_SETTINGS, loadSettings } from '../settings.js'
import { icons, morphIcon, setIcon } from '../components/icons.js'
import { bridgeCall } from '../webstatus.js'
import type { AppSettings } from '../settings.js'
import type { CachedChapter } from '../types.js'

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

const fmtMb = (mb: number): string => (mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb} MB`)

const fmtBytes = (bytes: number): string => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

export function settingsPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'settings-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">设置</h1>
      <p class="page-sub">改完点「保存」写回 config.yaml</p>
    </header>
    <p class="settings-note">保存后写进 <code>config.yaml</code>（打包版在 <code>~/.jmreader</code> 里）；
      标了「重启生效」的要重开窗口才用得上。</p>
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

    <section class="settings-block">
      <h2 class="block-title">更新</h2>
      <p class="block-note">只热更<strong>前端</strong>（页面与素材）：装完刷新页面就生效，安装包一行都不动，不用重新安装。</p>
      <p class="version-line"></p>
      <div class="settings-actions">
        <button type="button" class="check-update-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>检查更新</span></button>
        <button type="button" class="apply-update-btn" hidden><morph-icon size="16" stroke-width="1.8"></morph-icon><span>立即更新</span></button>
        <button type="button" class="rollback-btn" hidden><morph-icon size="16" stroke-width="1.8"></morph-icon><span>退回上一版</span></button>
        <button type="button" class="open-web-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>打开前端目录</span></button>
      </div>
      <p class="update-status"></p>
      <pre class="update-notes" hidden></pre>
    </section>

    <section class="settings-block">
      <h2 class="block-title">磁盘</h2>
      <p class="disk-line"></p>
      <div class="settings-actions">
        <button type="button" class="open-data-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>打开数据目录</span></button>
        <button type="button" class="open-dl-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>打开下载目录</span></button>
      </div>
      <details class="disk-detail">
        <summary>磁盘上有哪几话</summary>
        <div class="disk-list"></div>
      </details>
    </section>

    <section class="settings-block">
      <h2 class="block-title">桌面集成</h2>
      <p class="block-note">开关在上面那张表的「桌面集成」里改，这一行是<strong>实际</strong>状态：托盘起没起、快捷键注册上没有。</p>
      <p class="desktop-line"></p>
      <div class="settings-actions">
        <button type="button" class="desktop-reload-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>重读状态</span></button>
      </div>
    </section>

    <section class="settings-block">
      <h2 class="block-title">数据</h2>
      <p class="block-note">收藏、阅读记录、设置都能导成一个 JSON 文件：换机器、重装、备份用得上（图片不导，那是再生资源）。</p>
      <div class="settings-actions">
        <button type="button" data-export="favorites">导出收藏</button>
        <button type="button" data-export="history">导出阅读记录</button>
        <button type="button" data-export="settings">导出设置</button>
        <button type="button" data-export="all">全部导出</button>
        <button type="button" class="import-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>导入…</span></button>
      </div>
      <p class="data-status"></p>
    </section>

    <section class="settings-block">
      <h2 class="block-title">日志</h2>
      <p class="block-note">出问题时把日志发出来最快（日志按天切，留 7 天）。</p>
      <div class="settings-actions">
        <button type="button" class="log-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>看日志尾巴</span></button>
        <button type="button" class="open-logs-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>打开日志目录</span></button>
      </div>
      <pre class="log-box" hidden></pre>
    </section>

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
  setIcon(el, '.check-update-btn morph-icon', icons.update)
  setIcon(el, '.apply-update-btn morph-icon', icons.download)
  setIcon(el, '.rollback-btn morph-icon', icons.back)
  setIcon(el, '.open-web-btn morph-icon', icons.folder)
  setIcon(el, '.open-data-btn morph-icon', icons.folder)
  setIcon(el, '.open-dl-btn morph-icon', icons.folder)
  setIcon(el, '.import-btn morph-icon', icons.upload)
  setIcon(el, '.log-btn morph-icon', icons.log)
  setIcon(el, '.open-logs-btn morph-icon', icons.folder)
  setIcon(el, '.desktop-reload-btn morph-icon', icons.reload)
  const usageEl = el.querySelector<HTMLElement>('.cache-usage')!
  const diskEl = el.querySelector<HTMLElement>('.disk-line')!
  const versionEl = el.querySelector<HTMLElement>('.version-line')!
  const updateStatusEl = el.querySelector<HTMLElement>('.update-status')!
  const updateNotesEl = el.querySelector<HTMLPreElement>('.update-notes')!
  const dataStatusEl = el.querySelector<HTMLElement>('.data-status')!
  const logBoxEl = el.querySelector<HTMLPreElement>('.log-box')!
  const diskDetailEl = el.querySelector<HTMLDetailsElement>('.disk-detail')!
  const diskListEl = el.querySelector<HTMLElement>('.disk-list')!
  const desktopLineEl = el.querySelector<HTMLElement>('.desktop-line')!
  const applyBtn = el.querySelector<HTMLButtonElement>('.apply-update-btn')!
  const rollbackBtn = el.querySelector<HTMLButtonElement>('.rollback-btn')!
  const api = () => window.pywebview?.api

  /** 建控件：kind 由后端那张表说了算 */
  function buildRow(field: SettingsField, section: string): HTMLElement {
    const path = `${section}.${field.key}`
    const row = document.createElement('div')
    row.className = 'settings-row'

    const label = document.createElement('label')
    label.textContent = field.label
    row.appendChild(label)

    if (field.kind === 'bool') {
      const input = document.createElement('input')
      input.type = 'checkbox'
      input.dataset.path = path
      row.appendChild(input)
    } else if (field.kind === 'enum') {
      const select = document.createElement('select')
      select.dataset.path = path
      for (const option of field.options ?? []) {
        const item = document.createElement('option')
        item.value = option
        item.textContent = option
        select.appendChild(item)
      }
      row.appendChild(select)
    } else if (field.kind === 'int_pair') {
      for (const index of [0, 1]) {
        const input = document.createElement('input')
        input.type = 'number'
        input.dataset.path = path
        input.dataset.index = String(index)
        if (field.min !== undefined) input.min = String(field.min)
        if (field.max !== undefined) input.max = String(field.max)
        row.appendChild(input)
      }
    } else {
      const input = document.createElement('input')
      input.type = field.kind === 'int' || field.kind === 'float' ? 'number' : 'text'
      input.dataset.path = path
      if (field.min !== undefined) input.min = String(field.min)
      if (field.max !== undefined) input.max = String(field.max)
      if (field.step !== undefined) input.step = String(field.step)
      if (field.key === 'url' || field.key === 'dir') input.className = 'wide'
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

  function buildForm(spec: SettingsSpec): void {
    formEl.innerHTML = ''
    for (const section of spec.sections) {
      const box = document.createElement('fieldset')
      const legend = document.createElement('legend')
      legend.textContent = section.label
      box.appendChild(legend)
      for (const field of section.fields) box.appendChild(buildRow(field, section.key))
      formEl.appendChild(box)
    }
  }

  function fill(settings: AppSettings): void {
    formEl.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-path]').forEach((input) => {
      const value = getByPath(settings, input.dataset.path!)
      const index = (input as HTMLInputElement).dataset.index
      if (input instanceof HTMLInputElement && input.type === 'checkbox') input.checked = Boolean(value)
      else if (index !== undefined) input.value = String((value as unknown[] | undefined)?.[Number(index)] ?? '')
      else input.value = value == null ? '' : String(value)
    })
  }

  /** 把表单收成和后端一样的嵌套结构（只收框里有的，没动的段后端不会碰） */
  function collect(): Record<string, any> {
    const payload: Record<string, any> = {}
    formEl.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-path]').forEach((input) => {
      const path = input.dataset.path!
      const index = (input as HTMLInputElement).dataset.index
      const value: unknown = input instanceof HTMLInputElement && input.type === 'checkbox'
        ? input.checked
        : input instanceof HTMLInputElement && input.type === 'number' ? Number(input.value) : input.value
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

  /** 缓存 + 磁盘两份账：一个 API 调用各拉一次，页面上合成几行 */
  async function refreshUsage(): Promise<void> {
    const current = api()
    if (!current?.get_cache_stats) {
      usageEl.textContent = ''
      return
    }
    try {
      const stats = await current.get_cache_stats()
      const limit = stats.limit_mb > 0 ? fmtMb(stats.limit_mb) : '不限'
      usageEl.textContent = `缓存已用 ${fmtMb(stats.used_mb)} / 上限 ${limit}（${stats.chapters} 话；每 ${stats.interval} 秒自动整理一次）`
      usageEl.classList.toggle('over', stats.limit_mb > 0 && stats.used_mb > stats.limit_mb)
    } catch (err) {
      usageEl.textContent = '缓存占用读取失败: ' + (err instanceof Error ? err.message : String(err))
    }
    if (!current.get_disk_usage) return
    try {
      const disk = await current.get_disk_usage()
      const free = disk.free_mb === null ? '取不到' : fmtMb(disk.free_mb)
      diskEl.textContent = `缓存 ${fmtMb(disk.cache_mb)} · 离线下载 ${fmtMb(disk.download_mb)}`
        + `（${disk.offline_chapters} 话） · 阅读记录与设置 ${disk.data_mb} MB · 这块盘还剩 ${free}`
    } catch (err) {
      diskEl.textContent = '磁盘占用读取失败: ' + (err instanceof Error ? err.message : String(err))
    }
  }

  /** 桌面集成的实际状态：托盘 / 通知 / 自启 / 快捷键（配置只是"想要什么"） */
  async function refreshDesktop(): Promise<void> {
    const current = api()
    if (!current?.get_desktop_state) {
      desktopLineEl.textContent = ''
      return
    }
    try {
      const state = await current.get_desktop_state()
      const windows = state.platform === 'win32'
      const parts = [
        `系统通知 ${state.notify ? '开' : '关'}`,
        windows
          ? `托盘 ${state.tray_live ? '已就绪' : state.tray ? '没起来（看日志）' : '关'}`
          : `托盘 只有 Windows 有`,
        `开机自启 ${state.autostart ? '已写入' : '没开'}`,
        state.hotkeys
          ? `全局快捷键 ${state.hotkey_toggle} ${state.hotkeys_live ? '已注册' : '没注册上（看日志）'}`
          : '全局快捷键 关',
      ]
      desktopLineEl.textContent = parts.join(' · ')
    } catch (err) {
      desktopLineEl.textContent = '桌面状态读取失败: ' + (err instanceof Error ? err.message : String(err))
    }
  }

  /** 磁盘上到底有哪几话：摊开的时候才去问一次（几千张图扫一遍，别跟着开页一起扫） */
  async function loadCachedList(): Promise<void> {
    const current = api()
    if (!current?.list_cached_chapters) return
    diskListEl.textContent = '读取中…'
    try {
      const list = await current.list_cached_chapters('', 200)
      diskListEl.textContent = ''
      if (list.length === 0) {
        diskListEl.textContent = '磁盘上一话都没有'
        return
      }
      for (const item of list) diskListEl.appendChild(cachedRow(item))
    } catch (err) {
      diskListEl.textContent = '读取失败: ' + (err instanceof Error ? err.message : String(err))
    }
  }

  /** 一话一行：哪本的第几话、几张、多大、"离线副本"还是"缓存"；点一下进这本详情 */
  function cachedRow(item: CachedChapter): HTMLElement {
    const row = document.createElement('div')
    row.className = 'disk-row'
    const name = document.createElement('span')
    name.className = 'disk-row-name'
    name.textContent = item.title || (item.index ? `第 ${item.index} 话` : item.photo_id)
    const book = document.createElement('span')
    book.className = 'disk-row-book'
    book.textContent = item.album_title || (item.offline ? '' : '随手缓存的')
    const size = document.createElement('span')
    size.className = 'disk-row-size'
    size.textContent = `${item.images} 张 · ${fmtBytes(item.bytes)}`
    const tag = document.createElement('span')
    tag.className = item.offline ? 'disk-tag offline' : 'disk-tag'
    tag.textContent = item.offline ? '离线副本' : '缓存'
    row.append(name, book, size, tag)
    if (item.album_id) {
      row.classList.add('clickable')
      row.title = '进这本的详情页'
      row.addEventListener('click', () => { window.location.hash = `#/album?id=${item.album_id}` })
    }
    return row
  }

  /** 版本与更新：当前 app / 前端版本 + 有没有新版 */
  let hasOverlay = false
  async function refreshVersion(check = false): Promise<void> {
    const current = api()
    if (!current?.get_version) {
      versionEl.textContent = '（读不到版本：pywebview api 未就绪）'
      return
    }
    try {
      const info = await current.get_version()
      hasOverlay = Boolean(info.overlay)
      versionEl.textContent = `安装包 ${info.app} · 前端 ${info.web || '出厂那份'}`
        + `（${info.update.enabled ? '更新通道开着' : '更新通道关着'}）`
      rollbackBtn.hidden = !hasOverlay
    } catch (err) {
      versionEl.textContent = '版本读取失败: ' + (err instanceof Error ? err.message : String(err))
    }
    if (!check) return
    await runCheck()
  }

  async function runCheck(): Promise<void> {
    const current = api()
    if (!current?.check_update) return
    updateStatusEl.textContent = '正在检查…'
    updateStatusEl.classList.remove('over')
    applyBtn.hidden = true
    updateNotesEl.hidden = true
    try {
      const info = await current.check_update()
      if (info.error) {
        updateStatusEl.textContent = `没查成：${info.error}`
        return
      }
      if (info.too_new) {
        updateStatusEl.textContent = `有新版前端（${info.version}），但它要 ${info.app_min} 以上的安装包，得去下新版安装包`
        return
      }
      if (info.available) {
        updateStatusEl.textContent = info.known_bad
          ? `有新版 ${info.version}，但这一版上次装上去没能开起来（已自动退回），先别急着重装`
          : `有新版前端 ${info.version}${info.size ? `（${fmtBytes(info.size)}）` : ''}`
        applyBtn.hidden = Boolean(info.known_bad)
        if (info.notes) {
          updateNotesEl.textContent = info.notes
          updateNotesEl.hidden = false
        }
      } else {
        updateStatusEl.textContent = `已经是最新的（前端 ${info.current_web || '出厂那份'}）`
      }
    } catch (err) {
      updateStatusEl.textContent = '检查失败: ' + (err instanceof Error ? err.message : String(err))
    }
  }

  async function refresh(): Promise<void> {
    if (!api()) {
      statusEl.textContent = 'pywebview api 未就绪'
      return
    }
    reloadIco.classList.add('spin')
    try {
      const [spec] = await Promise.all([
        bridgeCall('get_settings_spec', []),
        loadSettings(true),
      ])
      buildForm(spec)
      fill(await loadSettings(true))
      statusEl.textContent = ''
      void refreshUsage()
      void refreshVersion(false)
      void refreshDesktop()
    } catch (err) {
      statusEl.textContent = '读取设置失败: ' + (err instanceof Error ? err.message : String(err))
    } finally {
      reloadIco.classList.remove('spin')
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
        void refreshVersion(false)
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

  // ---- 更新 ----
  el.querySelector('.check-update-btn')!.addEventListener('click', () => { void runCheck() })

  applyBtn.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.apply_update) return
      applyBtn.disabled = true
      updateStatusEl.textContent = '正在下载并安装…'
      try {
        const res = await current.apply_update(false)
        updateStatusEl.textContent = res.changed
          ? `装好了：前端 ${res.version}（${res.files} 个文件）。正在刷新页面…`
          : '本来就没有新版'
        if (res.changed) window.setTimeout(() => window.location.reload(), 700)
      } catch (err) {
        updateStatusEl.textContent = '更新失败: ' + (err instanceof Error ? err.message : String(err))
      } finally {
        applyBtn.disabled = false
      }
    })()
  })

  rollbackBtn.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.rollback_update) return
      updateStatusEl.textContent = '正在退回…'
      try {
        await current.rollback_update()
        updateStatusEl.textContent = '退回上一版了。正在刷新页面…'
        window.setTimeout(() => window.location.reload(), 700)
      } catch (err) {
        updateStatusEl.textContent = '退回失败: ' + (err instanceof Error ? err.message : String(err))
      }
    })()
  })

  // ---- 打开目录 / 导入导出 / 日志 ----
  async function openFolder(kind: FolderKind): Promise<void> {
    const current = api()
    if (!current?.open_folder) return
    try {
      const res = await current.open_folder(kind)
      if (!res.opened) dataStatusEl.textContent = `没打开：${res.reason ?? ''}（${res.path}）`
    } catch (err) {
      dataStatusEl.textContent = '打不开：' + (err instanceof Error ? err.message : String(err))
    }
  }

  el.querySelector('.open-web-btn')!.addEventListener('click', () => { void openFolder('web') })
  el.querySelector('.open-data-btn')!.addEventListener('click', () => { void openFolder('app') })
  el.querySelector('.open-dl-btn')!.addEventListener('click', () => { void openFolder('downloads') })
  el.querySelector('.open-logs-btn')!.addEventListener('click', () => { void openFolder('logs') })

  for (const btn of el.querySelectorAll<HTMLButtonElement>('[data-export]')) {
    btn.addEventListener('click', () => {
      void (async () => {
        const current = api()
        if (!current?.export_data) return
        dataStatusEl.textContent = '导出中…'
        try {
          const res = await current.export_data(btn.dataset.export as ExportKind)
          dataStatusEl.textContent = res.cancelled
            ? '取消了'
            : `已导出 ${res.count ?? 0} 条到 ${res.path}（${fmtBytes(res.bytes ?? 0)}）`
        } catch (err) {
          dataStatusEl.textContent = '导出失败: ' + (err instanceof Error ? err.message : String(err))
        }
      })()
    })
  }

  el.querySelector('.import-btn')!.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.import_data) return
      dataStatusEl.textContent = '导入中…'
      try {
        const res = await current.import_data('', '')
        dataStatusEl.textContent = res.cancelled
          ? '取消了'
          : `已导入 ${res.imported ?? 0} 条（跳过 ${res.skipped ?? 0} 条）：${res.kind}`
        if (!res.cancelled) {
          void loadSettings(true).then((fresh) => fill(fresh))
          void refreshUsage()
        }
      } catch (err) {
        dataStatusEl.textContent = '导入失败: ' + (err instanceof Error ? err.message : String(err))
      }
    })()
  })

  // 明细是懒加载：摊开才去扫磁盘（一次点开就够了，别每次展开都重扫）
  let diskLoaded = false
  diskDetailEl.addEventListener('toggle', () => {
    if (!diskDetailEl.open || diskLoaded) return
    diskLoaded = true
    void loadCachedList()
  })

  el.querySelector('.desktop-reload-btn')!.addEventListener('click', () => { void refreshDesktop() })

  el.querySelector('.log-btn')!.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.get_log_tail) return
      if (!logBoxEl.hidden) {     // 再点一下收起来
        logBoxEl.hidden = true
        return
      }
      logBoxEl.hidden = false
      logBoxEl.textContent = '读取中…'
      try {
        const tail = await current.get_log_tail(200)
        logBoxEl.textContent = tail.error
          ? tail.error
          : `${tail.path}${tail.truncated ? '（只显示最后 2 MB）' : ''}\n\n${tail.lines.join('\n')}`
        logBoxEl.scrollTop = logBoxEl.scrollHeight
      } catch (err) {
        logBoxEl.textContent = '读日志失败: ' + (err instanceof Error ? err.message : String(err))
      }
    })()
  })

  fill(DEFAULT_SETTINGS)   // 先用默认值把表单铺出来（规范没到手之前别空着）
  void refresh()

  return el
}
