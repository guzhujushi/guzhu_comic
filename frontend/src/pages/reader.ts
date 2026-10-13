import { onUnmount } from '../router.js'
import { loadSettings } from '../settings.js'

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
    <div class="reader-toolbar">
      <button class="back-btn">← 返回</button>
      <span class="reader-title">加载中...</span>
      <span class="reader-page"></span>
    </div>
    <div class="reader-images"></div>
  `

  const titleEl = el.querySelector('.reader-title')!
  const pageEl = el.querySelector('.reader-page')!
  const imgsEl = el.querySelector<HTMLElement>('.reader-images')!
  const toolbarEl = el.querySelector<HTMLElement>('.reader-toolbar')!
  el.querySelector('.back-btn')!.addEventListener('click', () => history.back())

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
  const noteUserInput = () => { userInputAt = performance.now() }
  window.addEventListener('wheel', noteUserInput, { passive: true })
  window.addEventListener('touchmove', noteUserInput, { passive: true })

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
      clickToPage = settings.reader.click_to_page
      if (album) {
        title = album.title
        coverUrl = album.cover_url
      }
      titleEl.textContent = title || `章节 ${photoId}`
      renderImages()
      // 设置里关掉"自动回到上次那一页"就从第 1 页开始
      const start = settings.reader.restore_progress ? startIndex : 0
      currentIndex = Math.min(Math.max(0, start), Math.max(0, images.length - 1))
      progressReady = true
      updatePageLabel()
      // 必须等图片把高度撑起来之后再滚，否则 scrollIntoView 会被夹在顶部
      await restoreScroll()
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
    // 工具栏是 sticky 的，不把它的高度让出来，目标页顶部会被压在工具栏下面
    target.style.scrollMarginTop = `${toolbarEl.offsetHeight}px`
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

  /**
   * 存进度。页码只在翻页时才变，所以直接存、不做防抖：
   * 关窗口太快时，"1s 防抖"和 pagehide 里那次异步桥调用都来不及落库。
   */
  function saveProgress(): void {
    // 进度还没读出来时 currentIndex 还是 0；恢复过程中页码只是过渡值。
    // 这两种情况存下去都会把库里的真实进度抹掉（缺图时尤其明显：恢复到一半的页码
    // 会被当成新进度写进库）。
    if (!progressReady || restoring) return
    void window.pywebview?.api?.save_progress(albumId, photoId, currentIndex, title, coverUrl)
  }

  function goTo(i: number): void {
    if (!images.length) return
    restoreCancelled = true   // 用户主动翻页，别再把他拽回"上次那一页"
    restoring = false
    currentIndex = Math.max(0, Math.min(images.length - 1, i))
    scrollToIndex(currentIndex)
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
    } else if (e.key === 'Escape') {
      history.back()
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

  // 关窗口 / 刷新时 pagehide 会触发（路由切走不会）
  const onHide = () => saveProgress()
  window.addEventListener('pagehide', onHide)

  // 路由切走（点"返回"、改 hash）时收尾：存一次进度 + 解绑所有 window 监听
  onUnmount(() => {
    restoreCancelled = true
    saveProgress()
    window.removeEventListener('scroll', onScroll)
    window.removeEventListener('keydown', onKey)
    window.removeEventListener('pagehide', onHide)
    window.removeEventListener('wheel', noteUserInput)
    window.removeEventListener('touchmove', noteUserInput)
  })

  return el
}
