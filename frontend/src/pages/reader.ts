import { onUnmount } from '../router.js'
import { loadSettings } from '../settings.js'
import type { AppSettings } from '../settings.js'
import type { Chapter } from '../types.js'

type ReaderMode = 'webtoon' | 'single'

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
    <div class="reader-toolbar" data-visible="false">
      <div class="reader-nav">
        <button class="back-btn">← 返回</button>
        <button class="chapters-btn">章节</button>
        <button class="prev-btn">上一章</button>
        <button class="next-btn">下一章</button>
      </div>
      <span class="reader-title">加载中...</span>
      <div class="reader-nav">
        <span class="reader-page"></span>
        <button class="auto-btn" hidden title="自动滚屏">▶</button>
        <button class="settings-btn" title="阅读设置">⚙</button>
      </div>
    </div>
    <div class="reader-chapters" hidden></div>
    <div class="reader-settings" hidden></div>
    <div class="reader-images"></div>
  `

  const titleEl = el.querySelector('.reader-title')!
  const pageEl = el.querySelector('.reader-page')!
  const imgsEl = el.querySelector<HTMLElement>('.reader-images')!
  const toolbarEl = el.querySelector<HTMLElement>('.reader-toolbar')!
  const chaptersEl = el.querySelector<HTMLElement>('.reader-chapters')!
  const settingsEl = el.querySelector<HTMLElement>('.reader-settings')!
  const chaptersBtn = el.querySelector<HTMLButtonElement>('.chapters-btn')!
  const prevBtn = el.querySelector<HTMLButtonElement>('.prev-btn')!
  const nextBtn = el.querySelector<HTMLButtonElement>('.next-btn')!
  const autoBtn = el.querySelector<HTMLButtonElement>('.auto-btn')!
  el.querySelector('.back-btn')!.addEventListener('click', () => {
    flushProgress()
    history.back()
  })

  // 从详情页进来时窗口还停在上一个页面的滚动位置，先归零；
  // 具体恢复到第几页交给 restoreScroll（此刻图片还没高度，滚了也会被夹回顶部）
  window.scrollTo(0, 0)

  let images: string[] = []
  let title = ''
  let coverUrl = ''
  let currentIndex = 0
  let progressReady = false   // 上次进度读出来之前，currentIndex 是无意义的 0
  let clickToPage = true      // 点击左右两侧翻页，设置里可以关掉
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

  // 工具栏不常驻：鼠标动一下才出来，停手几秒自己缩回去；滚轮和方向键都不算（不然翻页时会一直闪）
  const HIDE_AFTER_MS = 2600
  let hideTimer = 0
  let pointerX = 0
  let pointerY = 0
  let pointerInside = false

  function hideToolbar(force = false): void {
    window.clearTimeout(hideTimer)
    if (pointerInside && !force) return
    toolbarEl.dataset.visible = 'false'
    chaptersEl.hidden = true
    settingsEl.hidden = true
  }

  function showToolbar(): void {
    toolbarEl.dataset.visible = 'true'
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

  // 在图上滚轮时把工具栏收掉；面板里自己滚不算
  const onWheel = (e: WheelEvent) => {
    if (toolbarEl.dataset.visible !== 'true') return
    const target = e.target as Node | null
    if (target && (toolbarEl.contains(target) || chaptersEl.contains(target) || settingsEl.contains(target))) return
    hideToolbar()
  }
  window.addEventListener('wheel', onWheel, { passive: true })

  for (const panel of [toolbarEl, chaptersEl, settingsEl]) {
    panel.addEventListener('mouseenter', () => { pointerInside = true; showToolbar() })
    panel.addEventListener('mouseleave', () => { pointerInside = false; showToolbar() })
  }

  let chapters: Chapter[] = []
  let chapterIndex = -1

  function goChapter(i: number): void {
    const next = chapters[i]
    if (next) window.location.hash = `#/read?photo_id=${next.photo_id}&album_id=${albumId}`
  }

  function updateNav(): void {
    const has = chapters.length > 0
    chaptersBtn.hidden = !has
    prevBtn.hidden = !has
    nextBtn.hidden = !has
    prevBtn.disabled = chapterIndex <= 0
    nextBtn.disabled = chapterIndex < 0 || chapterIndex >= chapters.length - 1
  }

  function renderChapters(): void {
    chaptersEl.innerHTML = ''
    for (const [i, ch] of chapters.entries()) {
      const btn = document.createElement('button')
      btn.className = 'chapter-item'
      if (i === chapterIndex) btn.classList.add('current')
      btn.textContent = ch.title || `第 ${ch.index} 话`   // 图源偶尔给空标题
      btn.addEventListener('click', () => { if (i === chapterIndex) hideToolbar(true); else goChapter(i) })
      chaptersEl.appendChild(btn)
    }
    updateNav()
  }

  chaptersBtn.addEventListener('click', () => {
    const open = chaptersEl.hidden
    settingsEl.hidden = true
    chaptersEl.hidden = !open
    showToolbar()
    if (open) chaptersEl.querySelector('.current')?.scrollIntoView({ block: 'nearest' })
  })

  el.querySelector('.settings-btn')!.addEventListener('click', () => {
    const open = settingsEl.hidden
    chaptersEl.hidden = true
    settingsEl.hidden = !open
    showToolbar()
  })

  prevBtn.addEventListener('click', () => goChapter(chapterIndex - 1))
  nextBtn.addEventListener('click', () => goChapter(chapterIndex + 1))

  // 阅读设置面板：改动立即生效，同时写回 config.yaml
  const MODES: [string, string][] = [['webtoon', '连续滚动'], ['single', '单页翻页']]
  const BACKGROUNDS: [string, string][] = [['dark', '深色'], ['black', '纯黑'], ['gray', '灰'], ['light', '浅色']]
  const toOptions = (items: [string, string][]) =>
    items.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')

  settingsEl.innerHTML = `
    <label class="reader-opt"><span>阅读模式</span><select class="opt-mode">${toOptions(MODES)}</select></label>
    <label class="reader-opt"><span>背景色</span><select class="opt-bg">${toOptions(BACKGROUNDS)}</select></label>
    <label class="reader-opt"><span>页间距</span><input class="opt-gap" type="number" min="0" max="64" /></label>
    <label class="reader-opt"><span>自动滚屏</span><input class="opt-auto" type="number" min="0" max="1000" /></label>
    <p class="reader-tip">页间距和自动滚屏只在「连续滚动」下有效，速度单位是像素/秒，0 就是关。自动滚屏时上方会出现 ⏯ 用来暂停 / 继续。</p>
    <label class="reader-opt"><input type="checkbox" class="opt-click" /> 点击左右两侧翻页</label>
    <label class="reader-opt"><input type="checkbox" class="opt-restore" /> 进章节时回到上次那一页</label>
    <a class="reader-opt-link" href="#/settings">更多设置 →</a>
  `
  const pick = <T extends HTMLElement>(sel: string) => settingsEl.querySelector<T>(sel)!
  const modeSel = pick<HTMLSelectElement>('.opt-mode')
  const bgSel = pick<HTMLSelectElement>('.opt-bg')
  const gapInput = pick<HTMLInputElement>('.opt-gap')
  const autoInput = pick<HTMLInputElement>('.opt-auto')
  const clickBox = pick<HTMLInputElement>('.opt-click')
  const restoreBox = pick<HTMLInputElement>('.opt-restore')

  function fillPanel(s: AppSettings): void {
    modeSel.value = s.reader.mode
    bgSel.value = s.reader.background
    gapInput.value = String(s.reader.page_gap)
    autoInput.value = String(s.reader.auto_scroll)
    clickBox.checked = s.reader.click_to_page
    restoreBox.checked = s.reader.restore_progress
  }
  void loadSettings().then(fillPanel)

  modeSel.addEventListener('change', () => { void saveReader({ mode: modeSel.value }) })
  bgSel.addEventListener('change', () => { void saveReader({ background: bgSel.value }) })
  gapInput.addEventListener('change', () => { void saveReader({ page_gap: Number(gapInput.value) }) })
  autoInput.addEventListener('change', () => { void saveReader({ auto_scroll: Number(autoInput.value) }) })
  clickBox.addEventListener('change', () => { void saveReader({ click_to_page: clickBox.checked }) })
  restoreBox.addEventListener('change', () => { void saveReader({ restore_progress: restoreBox.checked }) })

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
    if (!images.length) return
    scrollToIndex(currentIndex)
    if (autoSpeed > 0) setAutoScroll(true)
  }

  function applyReaderSettings(s: AppSettings): void {
    clickToPage = s.reader.click_to_page
    setBackground(s.reader.background)
    el.style.setProperty('--page-gap', `${s.reader.page_gap}px`)
    autoSpeed = s.reader.auto_scroll
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
    autoBtn.textContent = wanted ? '⏸' : '▶'
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
      // 设置里关掉"自动回到上次那一页"就从第 1 页开始
      const start = settings.reader.restore_progress ? startIndex : 0
      currentIndex = Math.min(Math.max(0, start), Math.max(0, images.length - 1))
      progressReady = true
      updatePageLabel()
      if (mode === 'single') updateSingleView()
      // 连续滚动要等图片把高度撑起来之后再滚，否则 scrollIntoView 会被夹在顶部
      else await restoreScroll()
      if (autoSpeed > 0) setAutoScroll(true)
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

  function scrollToIndex(i: number): void {
    const target = imgsEl.children[i] as HTMLElement | undefined
    if (!target) return
    // 工具栏浮在顶上，露出来时要把它的高度让出来，否则目标页顶部被压在下面
    target.style.scrollMarginTop = toolbarEl.dataset.visible === 'true' ? `${toolbarEl.offsetHeight}px` : '0px'
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
    pageEl.textContent = images.length ? `${currentIndex + 1} / ${images.length}` : ''
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
    } else if (mode === 'single' && (e.key === 'ArrowDown' || e.key === 'PageDown')) {
      e.preventDefault()
      goTo(currentIndex + 1)
    } else if (mode === 'single' && (e.key === 'ArrowUp' || e.key === 'PageUp')) {
      e.preventDefault()
      goTo(currentIndex - 1)
    } else if (e.key === 'Escape') {
      flushProgress()
      history.back()
    } else if (e.key === 'm' || e.key === 'M') {
      if (toolbarEl.dataset.visible === 'true') hideToolbar(true)
      else showToolbar()
    }
  }
  window.addEventListener('keydown', onKey)

  // 点击左右 30% 区域翻页，中间不动（设置里可以关）
  imgsEl.addEventListener('click', (e) => {
    if (!clickToPage) return
    const x = e.clientX / window.innerWidth
    if (x < 0.3) goTo(currentIndex - 1)
    else if (x > 0.7) goTo(currentIndex + 1)
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
    flushProgress()
    window.clearTimeout(hideTimer)
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
