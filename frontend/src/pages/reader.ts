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
  el.querySelector('.back-btn')!.addEventListener('click', () => history.back())

  let images: string[] = []
  let title = ''
  let coverUrl = ''
  let currentIndex = 0
  let saveTimer: number | undefined
  let isRestoring = true

  void (async () => {
    if (!window.pywebview?.api) {
      imgsEl.innerHTML = '<p class="empty-hint">pywebview api 未就绪</p>'
      return
    }
    try {
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
      currentIndex = Math.min(startIndex, Math.max(0, images.length - 1))
      updatePageLabel()
      requestAnimationFrame(() => scrollToIndex(currentIndex))
    } catch (err) {
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
    target?.scrollIntoView({ block: 'start' })
  }
  // 替换原来的 requestAnimationFrame(() => scrollToIndex(currentIndex))
void restoreScroll()

async function restoreScroll(): Promise<void> {
  try{
    if (currentIndex === 0) return
    const ahead = [...imgsEl.querySelectorAll('img')].slice(0, currentIndex + 1)
    const timeout = new Promise((r) => setTimeout(r, 8000))
     await Promise.race([
        Promise.allSettled(ahead.map((i) => i.decode().catch(() => {}))),
        timeout,
    ])
    scrollToIndex(currentIndex)
}finally{
    isRestoring = false
}
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
        if (r.top < mid && r.bottom > mid) return i  // 真正压住中线的那张
        if (r.top < mid) candidate = i
    }
    return Math.max(0, imgs.length - 1)
  }

  // 滚动时更新页码 + 节流保存；页面被路由移除后自动解绑
  const onScroll = () => {
    if (!document.contains(el)) {
        window.removeEventListener('scroll', onScroll)
        return
    }
    if (isRestoring) return
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
    void window.pywebview?.api?.save_progress(albumId, photoId, currentIndex, title, coverUrl)
  }
  window.addEventListener('pagehide', onHide)

  return el
}
