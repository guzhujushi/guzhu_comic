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

  let images: string[] = []
  let title = ''
  let coverUrl = ''
  let currentIndex = 0
  let saveTimer: number | undefined
  let restoring = true      // 进度恢复完成前，滚动事件不许覆盖页码
  let suppressScroll = false
  let restoreCancelled = false

  void (async () => {
    try {
      if (!window.pywebview?.api) {
        imgsEl.innerHTML = '<p class="empty-hint">pywebview api 未就绪</p>'
        return
      }
      // 章节图片 + 上次进度并行拿；标题封面给 save_progress 用（详情有 24h 缓存，开销小）
      const [ch, startIndex, album] = await Promise.all([
        window.pywebview.api.get_chapter(photoId),
        window.pywebview.api.get_progress(albumId, photoId),
        albumId ? window.pywebview.api.get_album_detail(albumId).catch(() => null) : Promise.resolve(null),
      ])
      images = ch.images
      if (album) {
        title = album.title
        coverUrl = album.cover_url
      }
      titleEl.textContent = title || `章节 ${photoId}`
      renderImages()
      currentIndex = Math.min(Math.max(0, startIndex), Math.max(0, images.length - 1))
      updatePageLabel()
      // 必须等图片把高度撑起来之后再滚，否则 scrollIntoView 会被夹在顶部
      await restoreScroll()
    } catch (err) {
      imgsEl.innerHTML = `<p class="empty-hint">加载失败: ${String(err)}</p>`
    } finally {
      restoring = false
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
    suppressScroll = true
    // 工具栏是 sticky 的，不把它的高度让出来，目标页顶部会被压在工具栏下面
    target.style.scrollMarginTop = `${toolbarEl.offsetHeight}px`
    target.scrollIntoView({ block: 'start' })
    requestAnimationFrame(() => {
        requestAnimationFrame(() => { suppressScroll = false })
    })
  }
  /**
   * 恢复上次进度。要等 target 之前的图都拿到高度再滚：整页还没被图片撑开时
   * scrollIntoView 会被夹在顶部，症状就是"每次进来都回到第 1 页"。
   * 由上面的 IIFE 在拿到 startIndex 之后 await 调用；期间 restoring 保持 true。
   */
  async function restoreScroll(): Promise<void> {
    if (currentIndex <= 0) return   // 本来就是第 1 页，不用滚
    const ahead = [...imgsEl.querySelectorAll('img')].slice(0, currentIndex + 1)
    const deadline = Date.now() + 20000
    while (Date.now() < deadline && !restoreCancelled) {
      if (ahead.every((img) => img.complete && img.naturalHeight > 0)) break
      await new Promise((r) => setTimeout(r, 200))
    }
    if (restoreCancelled) return     // 用户自己滚了，别抢他的位置
    scrollToIndex(currentIndex)
    // 等自己这次滚动的事件派发完，再放开 restoring
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(null))))
  }


  function updatePageLabel(): void {
    pageEl.textContent = images.length ? `${currentIndex + 1} / ${images.length}` : ''
  }

  function scheduleSave(): void {
    if (saveTimer !== undefined) window.clearTimeout(saveTimer)
    saveTimer = window.setTimeout(() => {
      void window.pywebview?.api?.save_progress(albumId, photoId, currentIndex, title, coverUrl)
    }, 1000)
  }

  function goTo(i: number): void {
    if (!images.length) return
    currentIndex = Math.max(0, Math.min(images.length - 1, i))
    scrollToIndex(currentIndex)
    updatePageLabel()
    scheduleSave()
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
    if (suppressScroll) return
    if (restoring) {
      // 图片还没撑开时按可见位置算出来必然是 0，不能用它覆盖页码；
      // 这次事件要么是 scrollIntoView 漏出来的，要么是用户提前滚了 —— 放弃这次恢复
      restoreCancelled = true
      restoring = false
    }
    const i = currentVisibleIndex()
    if (i !== currentIndex) {
      currentIndex = i
      updatePageLabel()
    }
    scheduleSave()
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

  // 点击左右 30% 区域翻页，中间不动
  imgsEl.addEventListener('click', (e) => {
    const x = e.clientX / window.innerWidth
    if (x < 0.3) goTo(currentIndex - 1)
    else if (x > 0.7) goTo(currentIndex + 1)
  })

  // 切走/关闭页面时存一次
  const onHide = () => {
    // 进度还没恢复出来就关窗口/切路由时，currentIndex 还是初始的 0，
    // 这一存就把库里的真实进度抹成第 1 页了
    if (restoring) return
    void window.pywebview?.api?.save_progress(albumId, photoId, currentIndex, title, coverUrl)
  }
  window.addEventListener('pagehide', onHide)

  return el
}
