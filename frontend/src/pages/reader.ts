import { onUnmount } from '../router.js'
import { icons, morphIcon, setIcon } from '../components/icons.js'
import { loadSettings } from '../settings.js'
import { warmChapterStart } from '../prefetch.js'
import { currentTheme, setTheme } from '../theme.js'
import type { AppSettings } from '../settings.js'
import type { Chapter } from '../types.js'

type ReaderMode = 'webtoon' | 'single'

// 换话要整页重建，靠 sessionStorage 把"从哪边进来的"带过去，落地后提示一句
const FLASH_KEY = 'reader.flash'

export function readerPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.className = 'reader'

  const photoId = params.photo_id ?? ''
  const albumId = params.album_id ?? ''
  if (!photoId) {
    el.innerHTML = '<p class="empty-hint">缺少章节 ID</p>'
    return el
  }

  el.innerHTML = `
    <div class="reader-ruler"><span></span></div>
    <div class="reader-top" data-visible="false">
      <button class="back-btn reader-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>返回</span></button>
      <div class="reader-head">
        <span class="reader-title">加载中...</span>
        <span class="reader-page"></span>
      </div>
      <div class="reader-tools">
        <button class="auto-btn reader-btn icon-btn" hidden title="自动滚屏" aria-label="自动滚屏"><morph-icon size="16" stroke-width="1.8"></morph-icon></button>
      </div>
    </div>
    <div class="reader-dock" data-visible="false">
      <button class="prev-btn reader-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>上一话</span></button>
      <button class="chapters-btn reader-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>目录</span></button>
      <button class="next-btn reader-btn"><morph-icon size="16" stroke-width="1.8"></morph-icon><span>下一话</span></button>
      <button class="settings-btn reader-btn icon-btn" title="阅读设置" aria-label="阅读设置"><morph-icon size="16" stroke-width="1.8"></morph-icon></button>
    </div>
    <div class="reader-sheet reader-chapters" hidden></div>
    <div class="reader-sheet reader-settings" hidden></div>
    <div class="reader-images"></div>
    <div class="reader-end" hidden data-ready="false"></div>
    <p class="reader-toast" aria-live="polite"></p>
  `

  const titleEl = el.querySelector('.reader-title')!
  const pageEl = el.querySelector('.reader-page')!
  const imgsEl = el.querySelector<HTMLElement>('.reader-images')!
  const topEl = el.querySelector<HTMLElement>('.reader-top')!
  const dockEl = el.querySelector<HTMLElement>('.reader-dock')!
  const rulerEl = el.querySelector<HTMLElement>('.reader-ruler span')!
  const chaptersEl = el.querySelector<HTMLElement>('.reader-chapters')!
  const settingsEl = el.querySelector<HTMLElement>('.reader-settings')!
  const endEl = el.querySelector<HTMLElement>('.reader-end')!
  const toastEl = el.querySelector<HTMLElement>('.reader-toast')!
  const chaptersBtn = el.querySelector<HTMLButtonElement>('.chapters-btn')!
  const prevBtn = el.querySelector<HTMLButtonElement>('.prev-btn')!
  const nextBtn = el.querySelector<HTMLButtonElement>('.next-btn')!
  const autoBtn = el.querySelector<HTMLButtonElement>('.auto-btn')!
  setIcon(el, '.back-btn morph-icon', icons.back)
  const chaptersIco = setIcon(el, '.chapters-btn morph-icon', icons.chapters)
  setIcon(el, '.prev-btn morph-icon', icons.prev)
  setIcon(el, '.next-btn morph-icon', icons.next)
  const autoIco = setIcon(el, '.auto-btn morph-icon', icons.play)
  const settingsIco = setIcon(el, '.settings-btn morph-icon', icons.settings)
  el.querySelector('.back-btn')!.addEventListener('click', () => {
    flushProgress()
    history.back()
  })

  // 阅读时收起左侧导航，退出时 onUnmount 再放回来
  document.body.classList.add('reading')

  // 从详情页进来时窗口还停在上一个页面的滚动位置，先归零；
  // 具体恢复到第几页交给 restoreScroll（此刻图片还没高度，滚了也会被夹回顶部）
  window.scrollTo(0, 0)

  let images: string[] = []
  let title = ''
  let coverUrl = ''
  let currentIndex = 0
  let progressReady = false   // 上次进度读出来之前，currentIndex 是无意义的 0
  let clickToPage = true      // 点击左右两侧翻页，设置里可以关掉
  let prefetchNextAt = 0      // 一话看到多少（0~1）就预加载下一话，来自 config 的 prefetch.next_at
  let warmedNext = false      // 这一话的「预热下一话」只触发一次
  let restoreCancelled = false
  let restoring = false       // 正在滚回上次那页，这期间的页码只是过渡值
  // 我们自己滚到的位置：scroll 事件里拿它比对，用来区分"我们滚的"和"用户滚的"
  let ownScrollY: number | null = null
  // 上面的图到货把版面撑开时，浏览器会自己修正滚动位置并派发一次 scroll 事件。
  // 这两个时间戳用来把"版面变化顺带滚的"和"用户真的在滚"分开。
  let lastLayoutChangeAt = 0
  let userInputAt = 0
  let mode: ReaderMode = 'webtoon' as ReaderMode
  let modeApplied = false
  let autoSpeed = 0          // 自动滚屏速度，像素/秒，0 = 关
  let autoRunning = false
  let autoTimer = 0
  let lastAutoAt = 0
  let lastFlipAt = 0
  const noteUserInput = () => {
    userInputAt = performance.now()
    if (autoRunning) setAutoScroll(false)   // 用户自己动手了就停自动滚屏
  }
  window.addEventListener('wheel', noteUserInput, { passive: true })
  window.addEventListener('touchmove', noteUserInput, { passive: true })

  // 上下两条工具条都不常驻：鼠标动一下才出来，停手几秒自己缩回去；
  // 滚轮和方向键都不算（不然翻页时会一直闪）
  const HIDE_AFTER_MS = 2600
  const bars = [topEl, dockEl]
  let hideTimer = 0
  let pointerX = 0
  let pointerY = 0
  let pointerInside = false

  const sheetOpen = () => !chaptersEl.hidden || !settingsEl.hidden
  const toolbarVisible = () => topEl.dataset.visible === 'true'

  function hideToolbar(force = false): void {
    window.clearTimeout(hideTimer)
    // 面板开着就别偷偷收，不然正挑着章节呢就没了
    if (!force && (pointerInside || sheetOpen())) return
    for (const bar of bars) bar.dataset.visible = 'false'
    openSheet(null, false)
  }

  function showToolbar(): void {
    for (const bar of bars) bar.dataset.visible = 'true'
    window.clearTimeout(hideTimer)
    hideTimer = window.setTimeout(hideToolbar, HIDE_AFTER_MS)
  }

  const onMouseMove = (e: MouseEvent) => {
    if (Math.abs(e.clientX - pointerX) + Math.abs(e.clientY - pointerY) < 6) return   // 轻微抖动不算
    pointerX = e.clientX
    pointerY = e.clientY
    showToolbar()
  }
  window.addEventListener('mousemove', onMouseMove, { passive: true })

  // 在图上滚轮时把工具条收掉；面板里自己滚不算
  const onWheel = (e: WheelEvent) => {
    if (!toolbarVisible()) return
    const target = e.target as Node | null
    if (target && (topEl.contains(target) || dockEl.contains(target) || chaptersEl.contains(target) || settingsEl.contains(target))) return
    hideToolbar(true)
  }
  window.addEventListener('wheel', onWheel, { passive: true })

  for (const panel of [topEl, dockEl, chaptersEl, settingsEl]) {
    panel.addEventListener('mouseenter', () => { pointerInside = true; showToolbar() })
    panel.addEventListener('mouseleave', () => { pointerInside = false; showToolbar() })
  }

  let chapters: Chapter[] = []
  let chapterIndex = -1

  function goChapter(i: number): void {
    const next = chapters[i]
    if (!next) return
    sessionStorage.setItem(FLASH_KEY, i > chapterIndex ? 'next' : 'prev')
    window.location.hash = `#/read?photo_id=${next.photo_id}&album_id=${albumId}`
  }

  function backToAlbum(): void {
    flushProgress()
    if (albumId) window.location.hash = `#/album?id=${albumId}`
    else history.back()
  }

  function updateNav(): void {
    const has = chapters.length > 0
    chaptersBtn.hidden = !has
    prevBtn.hidden = !has
    nextBtn.hidden = !has
    prevBtn.disabled = chapterIndex <= 0
    nextBtn.disabled = chapterIndex < 0 || chapterIndex >= chapters.length - 1
  }

  // 目录做成数字格子：图源动辄几百话，一列标题滚起来太累
  function renderChapters(): void {
    chaptersEl.innerHTML = `
      <div class="sheet-head">
        <span class="sheet-title">目录</span>
        <span class="sheet-sub"></span>
        <button class="sheet-close" aria-label="关闭"><morph-icon size="14" stroke-width="1.8"></morph-icon></button>
      </div>
      <div class="sheet-body chapter-grid"></div>
    `
    chaptersEl.querySelector('.sheet-sub')!.textContent = `共 ${chapters.length} 话`
    setIcon(chaptersEl, '.sheet-close morph-icon', icons.close)
    chaptersEl.querySelector('.sheet-close')!.addEventListener('click', () => openSheet(null))
    const grid = chaptersEl.querySelector<HTMLElement>('.chapter-grid')!
    for (const [i, ch] of chapters.entries()) {
      const btn = document.createElement('button')
      btn.className = 'chapter-cell'
      if (i === chapterIndex) btn.classList.add('current')
      btn.textContent = ch.index || String(i + 1)
      btn.title = ch.title || `第 ${i + 1} 话`   // 图源偶尔给空标题
      btn.addEventListener('click', () => { if (i === chapterIndex) openSheet(null); else goChapter(i) })
      grid.appendChild(btn)
    }
    updateNav()
  }

  // 目录和阅读设置共用一个底部浮层，同一时间只开一个
  function openSheet(name: 'chapters' | 'settings' | null, keep = true): void {
    chaptersEl.hidden = name !== 'chapters'
    settingsEl.hidden = name !== 'settings'
    morphIcon(chaptersIco, name === 'chapters' ? icons.close : icons.chapters)
    morphIcon(settingsIco, name === 'settings' ? icons.close : icons.settings)
    if (!name || !keep) return
    showToolbar()
    if (name === 'chapters') chaptersEl.querySelector('.current')?.scrollIntoView({ block: 'center' })
  }

  chaptersBtn.addEventListener('click', () => openSheet(chaptersEl.hidden ? 'chapters' : null))
  el.querySelector('.settings-btn')!.addEventListener('click', () => openSheet(settingsEl.hidden ? 'settings' : null))
  prevBtn.addEventListener('click', () => goChapter(chapterIndex - 1))
  nextBtn.addEventListener('click', () => goChapter(chapterIndex + 1))

  // 阅读设置面板：改动立即生效，同时写回 config.yaml
  const MODES: [string, string][] = [['webtoon', '连续滚动'], ['single', '单页翻页']]
  const BACKGROUNDS: [string, string][] = [['dark', '深色'], ['black', '纯黑'], ['gray', '灰'], ['light', '浅色']]
  const THEMES: [string, string][] = [['dark', '深色'], ['light', '浅色']]
  const toOptions = (items: [string, string][]) =>
    items.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')

  settingsEl.innerHTML = `
    <div class="sheet-head">
      <span class="sheet-title">阅读设置</span>
      <span class="sheet-sub">改完立即生效</span>
      <button class="sheet-close" aria-label="关闭"><morph-icon size="14" stroke-width="1.8"></morph-icon></button>
    </div>
    <div class="sheet-body">
      <div class="opt-grid">
        <label class="reader-opt"><span>阅读模式</span><select class="opt-mode">${toOptions(MODES)}</select></label>
        <label class="reader-opt"><span>背景色</span><select class="opt-bg">${toOptions(BACKGROUNDS)}</select></label>
        <label class="reader-opt"><span>界面主题</span><select class="opt-theme">${toOptions(THEMES)}</select></label>
        <label class="reader-opt"><span>页间距</span><input class="opt-gap" type="number" min="0" max="64" /></label>
        <label class="reader-opt"><span>图片宽度</span><input class="opt-width" type="number" min="0" max="2400" /></label>
        <label class="reader-opt"><span>自动滚屏</span><input class="opt-auto" type="number" min="0" max="1000" /></label>
      </div>
      <p class="reader-tip">图片宽度是漫画列的最大宽度，0 就是铺满窗口。页间距和自动滚屏只在「连续滚动」下有效，速度单位是像素/秒，0 就是关；自动滚屏时顶部会出现 ⏯ 用来暂停 / 继续。</p>
      <div class="opt-grid">
        <label class="reader-opt"><input type="checkbox" class="opt-click" /> 点击左右两侧翻页</label>
        <label class="reader-opt"><input type="checkbox" class="opt-restore" /> 进章节时回到上次那一页</label>
      </div>
      <p class="reader-keys"><kbd>←</kbd><kbd>→</kbd> 翻页<span class="keys-sep">·</span><kbd>空格</kbd> 下一页<span class="keys-sep">·</span><kbd>Home</kbd><kbd>End</kbd> 首尾<span class="keys-sep">·</span><kbd>M</kbd> 工具栏<span class="keys-sep">·</span><kbd>Esc</kbd> 返回</p>
      <a class="reader-opt-link" href="#/settings">更多设置 →</a>
    </div>
  `
  setIcon(settingsEl, '.sheet-close morph-icon', icons.close)
  settingsEl.querySelector('.sheet-close')!.addEventListener('click', () => openSheet(null))

  const pick = <T extends HTMLElement>(sel: string) => settingsEl.querySelector<T>(sel)!
  const modeSel = pick<HTMLSelectElement>('.opt-mode')
  const bgSel = pick<HTMLSelectElement>('.opt-bg')
  const themeSel = pick<HTMLSelectElement>('.opt-theme')
  const gapInput = pick<HTMLInputElement>('.opt-gap')
  const widthInput = pick<HTMLInputElement>('.opt-width')
  const autoInput = pick<HTMLInputElement>('.opt-auto')
  const clickBox = pick<HTMLInputElement>('.opt-click')
  const restoreBox = pick<HTMLInputElement>('.opt-restore')

  function fillPanel(s: AppSettings): void {
    modeSel.value = s.reader.mode
    bgSel.value = s.reader.background
    gapInput.value = String(s.reader.page_gap)
    widthInput.value = String(s.reader.width)
    autoInput.value = String(s.reader.auto_scroll)
    clickBox.checked = s.reader.click_to_page
    restoreBox.checked = s.reader.restore_progress
  }
  void loadSettings().then(fillPanel)

  modeSel.addEventListener('change', () => { void saveReader({ mode: modeSel.value }) })
  bgSel.addEventListener('change', () => { void saveReader({ background: bgSel.value }) })
  gapInput.addEventListener('change', () => { void saveReader({ page_gap: Number(gapInput.value) }) })
  widthInput.addEventListener('change', () => { void saveReader({ width: Number(widthInput.value) }) })
  autoInput.addEventListener('change', () => { void saveReader({ auto_scroll: Number(autoInput.value) }) })
  clickBox.addEventListener('change', () => { void saveReader({ click_to_page: clickBox.checked }) })
  restoreBox.addEventListener('change', () => { void saveReader({ restore_progress: restoreBox.checked }) })

  // 界面主题跟 config.yaml 无关（只记在本机），所以不走 saveReader，也不进 fillPanel
  themeSel.value = currentTheme()
  themeSel.addEventListener('change', () => {
    const next = themeSel.value === 'light' ? 'light' : 'dark'
    setTheme(themeSel, next)
  })

  async function saveReader(partial: Record<string, unknown>): Promise<void> {
    const api = window.pywebview?.api
    if (!api) return
    try {
      await api.save_settings({ reader: partial })
      const saved = await loadSettings(true)
      fillPanel(saved)
      applyReaderSettings(saved)
    } catch (err) {
      console.error('保存阅读设置失败', err)
    }
  }

  function setBackground(bg: string): void {
    document.documentElement.dataset.readerBg = bg
  }

  // 单页模式一次只显示一张，靠 .current 切换
  function updateSingleView(): void {
    ;[...imgsEl.children].forEach((img, i) => img.classList.toggle('current', i === currentIndex))
    syncEnd()
  }

  // 连续滚动时"下一话"卡片就摆在图后面；单页模式没有"图后面"，只在最后一页浮出来
  function syncEnd(): void {
    if (endEl.dataset.ready !== 'true') { endEl.hidden = true; return }
    endEl.hidden = mode === 'single' && currentIndex < images.length - 1
  }

  function setMode(next: ReaderMode): void {
    if (modeApplied && mode === next) return
    modeApplied = true
    mode = next
    el.dataset.mode = next
    if (next === 'single') {
      setAutoScroll(false)
      updateSingleView()
      return
    }
    syncEnd()
    if (!images.length) return
    scrollToIndex(currentIndex)
    if (autoSpeed > 0) setAutoScroll(true)
  }

  function applyReaderSettings(s: AppSettings): void {
    clickToPage = s.reader.click_to_page
    setBackground(s.reader.background)
    el.style.setProperty('--page-gap', `${s.reader.page_gap}px`)
    el.style.setProperty('--reader-col', s.reader.width > 0 ? `${s.reader.width}px` : '100%')
    autoSpeed = s.reader.auto_scroll
    prefetchNextAt = s.prefetch.next_at
    autoBtn.hidden = autoSpeed <= 0
    if (autoSpeed <= 0) setAutoScroll(false)
    setMode(s.reader.mode)
  }

  // 自动滚屏：按速度匀速往下推；用户动手、切到单页、或到底了就停（不自动跳下一章）
  function setAutoScroll(run: boolean): void {
    const wanted = run && autoSpeed > 0 && mode === 'webtoon'
    if (wanted === autoRunning) return
    autoRunning = wanted
    window.clearInterval(autoTimer)
    morphIcon(autoIco, wanted ? icons.pause : icons.play)
    if (wanted) {
      lastAutoAt = performance.now()
      autoTimer = window.setInterval(tickAutoScroll, 50)
    }
  }

  function tickAutoScroll(): void {
    const now = performance.now()
    const dt = Math.min(0.2, (now - lastAutoAt) / 1000)
    lastAutoAt = now
    if (restoring || !pageScrollable()) return   // 版面还没撑开，先别推
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) {
      setAutoScroll(false)
      return
    }
    window.scrollBy(0, autoSpeed * dt)
  }

  autoBtn.addEventListener('click', () => setAutoScroll(!autoRunning))

  // 整页还没被图片撑开时，滚动位置会被浏览器夹回顶部，算出来的页码没有意义
  function pageScrollable(): boolean {
    return document.documentElement.scrollHeight > window.innerHeight + 4
  }

  void (async () => {
    try {
      if (!window.pywebview?.api) {
        imgsEl.innerHTML = '<p class="empty-hint">pywebview api 未就绪</p>'
        return
      }
      // 章节图片 + 上次进度 + 配置并行拿；标题封面给 save_progress 用（详情有 24h 缓存，开销小）
      const [ch, startIndex, album, settings] = await Promise.all([
        window.pywebview.api.get_chapter(photoId),
        window.pywebview.api.get_progress(albumId, photoId),
        albumId ? window.pywebview.api.get_album_detail(albumId).catch(() => null) : Promise.resolve(null),
        loadSettings(),
      ])
      images = ch.images
      applyReaderSettings(settings)
      if (album) {
        title = album.title
        coverUrl = album.cover_url
        chapters = album.chapters ?? []
        chapterIndex = chapters.findIndex((c) => c.photo_id === photoId)
        renderChapters()
      }
      titleEl.textContent = title || `章节 ${photoId}`
      renderImages()
      renderEnd()
      // 设置里关掉"自动回到上次那一页"就从第 1 页开始
      const start = settings.reader.restore_progress ? startIndex : 0
      currentIndex = Math.min(Math.max(0, start), Math.max(0, images.length - 1))
      progressReady = true
      updatePageLabel()
      if (mode === 'single') updateSingleView()
      // 连续滚动要等图片把高度撑起来之后再滚，否则 scrollIntoView 会被夹在顶部
      else await restoreScroll()
      if (autoSpeed > 0) setAutoScroll(true)
      const flash = sessionStorage.getItem(FLASH_KEY)
      sessionStorage.removeItem(FLASH_KEY)
      if (flash === 'next') toast('已进入下一话')
      else if (flash === 'prev') toast('已进入上一话')
    } catch (err) {
      // 章节没加载出来就别动进度：progressReady 保持 false，后面所有存进度都会被跳过
      imgsEl.innerHTML = `<p class="empty-hint">加载失败: ${String(err)}</p>`
    }
  })()

  function armRetry(img: HTMLImageElement, src: string, attempts: number): void {
    img.onerror = () => {
        if (attempts >= 30 || !document.contains(img)) {
        img.onerror = null
        return
        }
        window.setTimeout(() => {
        if (!document.contains(img)) return
        armRetry(img, src, attempts + 1)
        img.src = `${src}?r=${attempts}`  // query 变化强制重新请求
        }, 2000)
    }
    }

  function renderImages(): void {
    imgsEl.innerHTML = ''
    images.forEach((src, i) => {
        const img = document.createElement('img')
        img.alt = `第 ${i + 1} 页`
        armRetry(img, src, 0)
        img.src = src
        imgsEl.appendChild(img)
    })
  }

  // 看完一话给个大按钮接着往下看，比让人自己摸回目录里找强
  function renderEnd(): void {
    const cur = chapterIndex >= 0 ? chapters[chapterIndex] : undefined
    const next = chapterIndex >= 0 ? chapters[chapterIndex + 1] : undefined
    endEl.dataset.ready = 'true'
    endEl.innerHTML = `
      <img class="reader-end-avatar" src="/apple-touch-icon.png" alt="" />
      <p class="reader-end-note"></p>
      ${next ? '<button class="end-next"><span></span><morph-icon size="16" stroke-width="1.8"></morph-icon></button>' : ''}
      <button class="end-back">${albumId ? '返回详情' : '返回上一页'}</button>
    `
    endEl.querySelector('.reader-end-note')!.textContent = cur?.title ? `已读完 ${cur.title}` : '本话读完了'
    if (next) {
      const btn = endEl.querySelector<HTMLButtonElement>('.end-next')!
      btn.querySelector('span')!.textContent = `下一话 · ${next.title || `第 ${next.index} 话`}`
      setIcon(endEl, '.end-next morph-icon', icons.next)
      btn.addEventListener('click', () => goChapter(chapterIndex + 1))
    }
    endEl.querySelector('.end-back')!.addEventListener('click', backToAlbum)
    syncEnd()
  }

  function scrollToIndex(i: number): void {
    const target = imgsEl.children[i] as HTMLElement | undefined
    if (!target) return
    // 顶部信息条浮在图上，露出来时要把它的高度让出来，否则目标页顶部被压在下面
    target.style.scrollMarginTop = toolbarVisible() ? `${topEl.offsetHeight}px` : '0px'
    target.scrollIntoView({ block: 'start' })
    ownScrollY = window.scrollY   // 这次的 scroll 事件不该被当成用户滚动
  }
  /** 元素在文档里的纵向位置（跟 offsetParent 是谁无关） */
  function docTop(el: HTMLElement): number {
    return el.getBoundingClientRect().top + window.scrollY
  }

  /**
   * 恢复上次进度。target 之前的图必须先拿到高度，否则目标页的位置是错的
   * （整页被撑开前 scrollIntoView 会被夹在顶部，症状就是"每次进来都回到第 1 页"）。
   * 但不能傻等：图还在后台下的时候前面的图迟迟不来，用户就对着第 1 页干等好几秒。
   * 所以先立刻滚一次，之后每当前面的图到货、版面变高，就把目标页重新钉回原位，
   * 直到目标之前的图全部就位、用户自己滚了、或等够 20s（恢复期间 restoring 为 true）。
   */
  async function restoreScroll(): Promise<void> {
    if (currentIndex <= 0) return   // 本来就是第 1 页，不用滚
    restoring = true
    try {
      const deadline = Date.now() + 20000
      let lastTop = Number.NaN
      while (!restoreCancelled && Date.now() < deadline) {
        const target = imgsEl.children[currentIndex] as HTMLElement | undefined
        if (!target) return
        const top = Math.round(docTop(target))
        if (top !== lastTop) {
          lastTop = top
          lastLayoutChangeAt = performance.now()
          scrollToIndex(currentIndex)
        }
        const ahead = [...imgsEl.querySelectorAll('img')].slice(0, currentIndex + 1)
        if (ahead.every((img) => img.complete && img.naturalHeight > 0)) return
        await new Promise((r) => setTimeout(r, 100))
      }
    } finally {
      restoring = false
    }
  }

  function updatePageLabel(): void {
    const total = images.length
    pageEl.textContent = total ? `${currentIndex + 1} / ${total}` : ''
    rulerEl.style.width = total ? `${((currentIndex + 1) / total) * 100}%` : '0%'
    maybeWarmNext()
  }

  /**
   * 一话看到 prefetch.next_at（默认 90%）就把下一话的开头几张先下下来，换话时不用等图。
   * 没有下一话、或者配置里关掉了，就什么都不做。页码每变一次都会走到这儿，
   * 所以第一件事是看 warmedNext（同一话只触发一次）。
   */
  function maybeWarmNext(): void {
    if (warmedNext || prefetchNextAt <= 0 || images.length === 0) return
    const next = chapterIndex >= 0 ? chapters[chapterIndex + 1] : undefined
    if (!next) return
    if ((currentIndex + 1) / images.length < prefetchNextAt) return
    warmedNext = true
    warmChapterStart(next.photo_id)
  }

  let toastTimer = 0
  function toast(text: string): void {
    window.clearTimeout(toastTimer)
    toastEl.textContent = text
    toastEl.classList.add('on')
    toastTimer = window.setTimeout(() => toastEl.classList.remove('on'), 2100)
  }

  let savedKey = ''   // 已经落库的那一页，避免重复写

  /**
   * 存进度。页码只在翻页时才变，所以直接存、不做防抖：
   * 关窗口太快时，"1s 防抖"和 pagehide 里那次异步桥调用都来不及落库。
   */
  function saveProgress(): void {
    // 进度还没读出来时 currentIndex 还是 0；恢复过程中页码只是过渡值。
    // 这两种情况存下去都会把库里的真实进度抹掉（缺图时尤其明显：恢复到一半的页码
    // 会被当成新进度写进库）。
    if (!progressReady || restoring) return
    const api = window.pywebview?.api
    const key = `${photoId}:${currentIndex}`
    if (!api || key === savedKey) return
    savedKey = key   // 同一页只写一次：返回按钮和路由收尾会各调一次
    void api.save_progress(albumId, photoId, currentIndex, title, coverUrl)
      .catch(() => { savedKey = '' })
  }

  function goTo(i: number): void {
    if (!images.length) return
    restoreCancelled = true   // 用户主动翻页，别再把他拽回"上次那一页"
    restoring = false
    setAutoScroll(false)      // 手动翻页就把自动滚屏停下
    currentIndex = Math.max(0, Math.min(images.length - 1, i))
    if (mode === 'single') updateSingleView()
    else scrollToIndex(currentIndex)
    updatePageLabel()
    saveProgress()
  }

  function currentVisibleIndex(): number {
    const mid = window.innerHeight / 2
    const imgs = imgsEl.querySelectorAll('img')
    let candidate = currentIndex
    for (let i = 0; i < imgs.length; i++) {
      const r = imgs[i].getBoundingClientRect()
      if (r.height === 0) continue        // 没加载出来，不参与计算
      if (r.top < mid && r.bottom > mid) return i
      if (r.bottom <= mid) candidate = i  // 中线上方最后一张有高度的
    }
    return candidate
  }
  // 滚动时更新页码 + 节流保存；页面被路由移除后自动解绑
  const onScroll = () => {
    if (!document.contains(el)) {
        window.removeEventListener('scroll', onScroll)
        return
    }
    if (mode === 'single') return   // 单页模式靠 currentIndex 定位，不看滚动位置
    // 以下三种 scroll 事件一律不算数：
    //   1. 我们自己滚出来的位置（scrollIntoView 恢复进度、键盘/点击翻页）；
    //   2. 进度还没从库里读出来：此刻 currentIndex 是初始的 0；
    //   3. 整页还没被图片撑开：滚动位置会被浏览器夹回顶部，算出来必然第 1 页
    //      —— 这就是"每次进章节都从第 1 页开始"的根因（路由换页时 #app 被清空、
    //      文档变矮、滚动被夹回，浏览器就会发这么一次事件）。
    // 反过来，只要页面已经能滚，用户的滚动就算数：立刻更新页码并落库。
    if (ownScrollY !== null && Math.abs(window.scrollY - ownScrollY) < 4) return
    // 排版刚被上面的图撑开过 -> 这次多半是浏览器顺带修正的位置，不是用户在滚；
    // 反之，版面没动而位置变了（拖滚动条）就是用户自己在滚。
    const now = performance.now()
    const userDriven = now - userInputAt < 400 || now - lastLayoutChangeAt > 300
    if (!progressReady || !pageScrollable() || !userDriven) return
    restoreCancelled = true   // 页面能滚了说明用户自己在动，放弃还没执行的恢复
    restoring = false         // 恢复过程就此结束，之后算出来的才是用户的真实进度
    const i = currentVisibleIndex()
    if (i !== currentIndex) {
      currentIndex = i
      updatePageLabel()
      saveProgress()
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true })

  // 键盘翻页
  const onKey = (e: KeyboardEvent) => {
    if (!document.contains(el)) {
      window.removeEventListener('keydown', onKey)
      return
    }
    if (e.key === 'ArrowRight' || e.key === ' ') {
      e.preventDefault()
      goTo(currentIndex + 1)
    } else if (e.key === 'ArrowLeft') {
      goTo(currentIndex - 1)
    } else if (e.key === 'Home') {
      e.preventDefault()
      goTo(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      goTo(images.length - 1)
    } else if (mode === 'single' && (e.key === 'ArrowDown' || e.key === 'PageDown')) {
      e.preventDefault()
      goTo(currentIndex + 1)
    } else if (mode === 'single' && (e.key === 'ArrowUp' || e.key === 'PageUp')) {
      e.preventDefault()
      goTo(currentIndex - 1)
    } else if (e.key === 'Escape') {
      // 面板开着先收面板，再按一次才退出
      if (sheetOpen()) openSheet(null)
      else {
        flushProgress()
        history.back()
      }
    } else if (e.key === 'm' || e.key === 'M') {
      if (toolbarVisible()) hideToolbar(true)
      else showToolbar()
    }
  }
  window.addEventListener('keydown', onKey)

  // 点左右 30% 翻页，中间点一下收 / 放工具条（左右翻页设置里可以关）
  imgsEl.addEventListener('click', (e) => {
    const x = e.clientX / window.innerWidth
    if (clickToPage && x < 0.3) { goTo(currentIndex - 1); return }
    if (clickToPage && x > 0.7) { goTo(currentIndex + 1); return }
    if (toolbarVisible()) hideToolbar(true)
    else showToolbar()
  })

  // 单页模式下滚轮就是翻页；连续滚动交给浏览器自己滚
  const onWheelFlip = (e: WheelEvent) => {
    if (mode !== 'single' || Math.abs(e.deltaY) < 6) return
    const now = performance.now()
    if (now - lastFlipAt < 140) return
    lastFlipAt = now
    goTo(currentIndex + (e.deltaY > 0 ? 1 : -1))
  }
  window.addEventListener('wheel', onWheelFlip, { passive: true })

  // 退出阅读的统一入口：先停掉还没跑完的恢复，再按屏幕上实际显示的那一页落库。
  // 恢复期间（restoring）平时不许写进度，退出时是例外 —— 否则图还没下完就返回，
  // 这一话的真实进度就丢了（库里的还是进来时那个旧页码）。
  function flushProgress(): void {
    if (!progressReady) return
    restoreCancelled = true
    restoring = false
    if (pageScrollable()) {
      const i = currentVisibleIndex()
      if (i !== currentIndex) {
        currentIndex = i
        updatePageLabel()
      }
    }
    saveProgress()
  }

  // 关窗口 / 刷新时 pagehide 会触发（路由切走不会）
  const onHide = () => flushProgress()
  window.addEventListener('pagehide', onHide)

  // 路由切走（点"返回"、改 hash）时收尾：存一次进度 + 解绑所有 window 监听
  onUnmount(() => {
    document.body.classList.remove('reading')
    flushProgress()
    window.clearTimeout(hideTimer)
    window.clearTimeout(toastTimer)
    window.clearInterval(autoTimer)
    delete document.documentElement.dataset.readerBg
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('wheel', onWheel)
    window.removeEventListener('wheel', onWheelFlip)
    window.removeEventListener('scroll', onScroll)
    window.removeEventListener('keydown', onKey)
    window.removeEventListener('pagehide', onHide)
    window.removeEventListener('wheel', noteUserInput)
    window.removeEventListener('touchmove', noteUserInput)
  })

  return el
}