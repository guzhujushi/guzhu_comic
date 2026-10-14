// pages/detail.ts
import { renderAlbumList } from '../components/album-list.js'
import { renderEmpty, renderError } from '../components/states.js'
import { icons, morphIcon, setIcon } from '../components/icons.js'
import { loadSettings } from '../settings.js'
import { warmChapterStart } from '../prefetch.js'
import { onUnmount } from '../router.js'
import { morphToReader } from '../motion.js'
import type { AppSettings } from '../settings.js'
import type { AlbumDetail, AlbumProgress, CommentItem, DownloadTask } from '../types.js'

export function albumPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.className = 'album-detail'

  const albumId = params.id ?? ''
  if (!albumId) {
    renderEmpty(el, {
      avatar: true,
      title: '缺少漫画 ID',
      hint: '从热门或者搜索里点一本进来吧',
      actionLabel: '去热门',
      onAction: () => { window.location.hash = '#/popular' },
    })
    return el
  }

  renderSkeleton(el)

  async function load(): Promise<void> {
    if (!window.pywebview?.api) {
      renderError(el, 'pywebview api 还没就绪', () => void load())
      return
    }
    try {
      const [data, progress, fav, cfg] = await Promise.all([
        window.pywebview.api.get_album_detail(albumId),
        // 读不到进度不影响看详情，按"没读过"处理
        window.pywebview.api.get_album_progress(albumId).catch(() => null),
        // 收藏态单独查本地表（不进详情缓存，那有 24h TTL）；查不到就当没收藏
        window.pywebview.api.is_favorite(albumId).catch(() => false),
        loadSettings(),
      ])
      renderDetail(data, progress, fav, cfg.detail, el)
    } catch (err) {
      renderError(el, String(err), () => {
        renderSkeleton(el)
        void load()
      })
    }
  }

  void load()

  return el
}

/** 下载按钮：整本下到本机（离线副本在 config.yaml 的 download.dir 里），标签跟任务状态走 */
function paintDownloadArea(container: HTMLElement, data: AlbumDetail): void {
  // 图源一话都没给的时候这一排压根不渲染，所以先认这一排在不在
  const actions = container.querySelector('.detail-actions')
  if (!actions) return
  const btn = actions.querySelector<HTMLButtonElement>('.download-btn')!
  const label = actions.querySelector<HTMLElement>('.download-label')!

  const iconEl = setIcon(actions, '.download-btn morph-icon', icons.download)
  const hintEl = container.querySelector<HTMLElement>('.fav-hint')!
  let iconKey = 'idle'
  let timer = 0

  // 路由切走就停表：详情页会被反复打开，定时器不能留着
  onUnmount(() => {
    if (timer) window.clearInterval(timer)
    timer = 0
  })

  function paint(task: DownloadTask | null): void {
    const state = task?.state
    const key = state === 'done' ? 'done' : task?.running ? 'busy' : 'idle'
    if (key !== iconKey) {
      iconKey = key   // 只在状态翻档时才变形，不然每两秒抖一次
      morphIcon(iconEl, key === 'done' ? icons.downloadDone
        : key === 'busy' ? icons.downloadBusy : icons.download)
    }
    label.textContent = key === 'done' ? '已下载'
      : key === 'busy' ? (task!.total ? `下载中 ${task!.done}/${task!.total} 话` : '下载中…')
        : task ? '继续下载' : '下载'
    btn.classList.toggle('on', key === 'done')
    btn.title = key === 'done' ? '已经下过整本；点一下重新校验缺的部分'
      : key === 'busy' ? '后台在下，关窗也留着，下次开窗接着下'
        : task ? (task.error || '接着下没下完的部分') : '整本下到本机，断网也能看'
    btn.disabled = false
  }

  async function poll(): Promise<void> {
    const api = window.pywebview?.api
    if (!api?.get_download) return
    if (timer) {
      window.clearInterval(timer)
      timer = 0
    }
    try {
      const task = await api.get_download(data.id)
      paint(task)
      // 还在下就盯着；下完了停表 —— 别让详情页一直问后端
      if (task?.running) timer = window.setInterval(() => void poll(), 2000)
    } catch {
      /* 下载态读不出来不影响看详情 */
    }
  }

  btn.addEventListener('click', () => {
    void (async () => {
      const api = window.pywebview?.api
      if (!api?.start_download) return
      btn.disabled = true
      try {
        // 话单直接从详情里拿：省一次"再问一遍图源"的往返
        const task = await api.start_download(data.id, data.title, data.cover_url ?? '',
          data.chapters.map((ch) => ({ photo_id: ch.photo_id, index: ch.index, title: ch.title })))
        paint(task)
        hintEl.textContent = ''
      } catch (err) {
        btn.disabled = false
        hintEl.textContent = `下载失败：${String(err).replace(/^Error:\s*/, '')}`
      }
      void poll()
    })()
  })

  void poll()
}

/** 详情骨架：封面块 + 几行文字，等详情接口回来再换成真内容 */
function renderSkeleton(container: HTMLElement): void {
  container.innerHTML = `
    <div class="detail-skeleton">
      <div class="skeleton sk-cover"></div>
      <div class="skeleton sk-line w-40"></div>
      <div class="skeleton sk-line w-24"></div>
      <div class="skeleton sk-block"></div>
    </div>
  `
}

/**
 * 点作者 / 标签就是「按这个条件搜一次」：搜索页认 `#/search?scope=…&q=…` 这两个地址参数
 * （范围 + 关键词），所以这里只负责拼一个能点的链接，不用再写点击逻辑。
 */
function searchHref(scope: 'author' | 'tag', value: string): string {
  return `#/search?scope=${scope}&q=${encodeURIComponent(value)}`
}

function renderDetail(
  data: AlbumDetail,
  progress: AlbumProgress | null,
  fav: boolean,
  cfg: AppSettings['detail'],
  container: HTMLElement,
): void {
  // 上次读到的那一话还在的话就接着读；列表里找不到（比如图源改了章节）就从第一话开始
  const resumeChapter = progress ? data.chapters.find((c) => c.photo_id === progress.photo_id) : undefined
  const startChapter = resumeChapter ?? data.chapters[0]
  // 进详情页就把「阅读按钮要打开的那一话」开头几张先下下来（看过的话磁盘上已经有，后端会跳过）
  if (startChapter) warmChapterStart(startChapter.photo_id)
  const readLabel = resumeChapter ? `继续阅读 · 第 ${progress!.page_index + 1} 页` : '开始阅读'

  // 封面地址同时喂给虚化层，引号先转义掉，免得把 CSS 里的 url() 拆坏
  const cover = (data.cover_url ?? '').replace(/"/g, '%22')
  const dates = dateLine(data)

  const collapseAfter = Math.max(0, cfg.chapters_collapse)   // 0 = 不折叠
  const commentPreview = Math.max(0, cfg.comment_preview)    // 0 = 不显示评论区
  const withSide = commentPreview > 0

  container.innerHTML = `
    <div class="detail-top">
      <button class="back-btn"><morph-icon size="15" stroke-width="1.8"></morph-icon><span>返回</span></button>
      <span class="fav-hint"></span>
      <button class="fav-btn" type="button"><morph-icon size="16" stroke-width="1.8"></morph-icon><span class="fav-label"></span></button>
    </div>
    <div class="detail-layout${withSide ? ' has-side' : ''}">
      <div class="detail-main">
        <div class="detail-hero">
          <img class="detail-cover" src="${cover}" alt="" />
          <h1 class="page-title detail-title">${escapeHtml(data.title)}</h1>
          <p class="detail-meta">作者：${data.author ? `<a class="meta-link" href="${searchHref('author', data.author)}">${escapeHtml(data.author)}</a>` : ''}</p>
          <p class="detail-meta">👀 ${escapeHtml(data.views)}　❤️ ${escapeHtml(data.likes)}　💬 ${escapeHtml(data.comment_count)}</p>
          ${dates ? `<p class="detail-meta">${escapeHtml(dates)}</p>` : ''}
          <div class="tags">${data.tags.map((t) => `<a class="tag" href="${searchHref('tag', t)}">${escapeHtml(t)}</a>`).join('')}</div>
        </div>
        ${startChapter ? `
        <div class="detail-actions">
          <button class="read-btn"><morph-icon size="18" stroke-width="1.8"></morph-icon><span>${readLabel}</span></button>
          <button class="download-btn" type="button"><morph-icon size="16" stroke-width="1.8"></morph-icon><span class="download-label">下载</span></button>
        </div>` : ''}
        <p class="desc">${escapeHtml(data.description)}</p>
        <h2 class="section-title">章节（${data.chapters.length}）</h2>
        <div class="chapter-list"></div>
        <div class="chapter-actions">
          <button type="button" class="chapter-more" hidden></button>
          <button type="button" class="chapter-jump" hidden></button>
        </div>
        ${data.related.length ? '<h2 class="section-title">相关作品</h2><div class="album-list related-list"></div>' : ''}
      </div>
      ${withSide ? '<aside class="detail-side"></aside>' : ''}
    </div>
  `

  // 虚化层用 --cover 当背景，一路渐隐到背景色
  if (cover) container.querySelector<HTMLElement>('.detail-hero')!.style.setProperty('--cover', `url("${cover}")`)

  setIcon(container, '.back-btn morph-icon', icons.back)
  const readBtn = container.querySelector('.read-btn')
  if (readBtn) setIcon(readBtn, 'morph-icon', icons.read)

  container.querySelector('.back-btn')!.addEventListener('click', () => history.back())
  paintFavorite(container, data, fav)

  // "开始阅读"/"继续阅读"：继续阅读直接跳到上次那一话，页码由阅读器自己恢复。
  // 走共享元素转场：封面那个矩形一路长成整屏阅读器（motion.ts 的 morphToReader）
  const coverEl = container.querySelector<HTMLElement>('.detail-cover')
  container.querySelector('.read-btn')?.addEventListener('click', () => {
    morphToReader(coverEl, `#/read?photo_id=${startChapter.photo_id}&album_id=${data.id}`)
  })

  paintDownloadArea(container, data)

  // 相关作品：卡片组件和列表页共用一个，点进去还是走 #/album 这条路由
  const relatedEl = container.querySelector<HTMLElement>('.related-list')
  if (relatedEl) {
    renderAlbumList(
      data.related.map((rel) => ({
        id: rel.id,
        title: rel.title || `漫画 ${rel.id}`,
        cover_url: rel.cover_url,
        subtitle: rel.author,
      })),
      relatedEl,
    )
  }

  paintChapters(container, data, resumeChapter, collapseAfter)

  const sideEl = container.querySelector<HTMLElement>('.detail-side')
  if (sideEl) void paintComments(sideEl, data.id, commentPreview)
}

/**
 * 收藏心形：点了先本地翻面（不等后端往返），写失败再翻回去。
 * 收藏态是本地表的一条记录，跟详情缓存无关，所以每次进详情都重新问一次。
 */
function paintFavorite(container: HTMLElement, data: AlbumDetail, fav: boolean): void {
  const btn = container.querySelector<HTMLButtonElement>('.fav-btn')!
  const hintEl = container.querySelector<HTMLElement>('.fav-hint')!
  const label = btn.querySelector<HTMLElement>('.fav-label')!
  const ico = setIcon(btn, 'morph-icon', fav ? icons.heartOn : icons.heart)

  let on = fav
  let busy = false

  const paint = (): void => {
    btn.classList.toggle('on', on)
    btn.title = on ? '取消收藏' : '加入收藏'
    label.textContent = on ? '已收藏' : '收藏'
    morphIcon(ico, on ? icons.heartOn : icons.heart)
  }
  paint()

  btn.addEventListener('click', () => {
    void (async () => {
      if (busy) return
      busy = true
      hintEl.textContent = ''
      const next = !on
      on = next
      paint()
      try {
        const api = window.pywebview?.api
        if (!api) throw new Error('pywebview api 还没就绪')
        // tag / 作者一起带上：收藏那一刻的快照（推荐画像用），不然过一天详情缓存过期就没了
        const saved = await api.toggle_favorite(
          data.id, data.title, data.cover_url ?? '', data.tags, data.authors)
        if (saved !== on) {   // 以后端返回的状态为准
          on = saved
          paint()
        }
      } catch (err) {
        on = !next
        paint()   // 回滚：界面别骗人
        hintEl.textContent = `收藏失败：${String(err).replace(/^Error:\s*/, '')}`
      } finally {
        busy = false
      }
    })()
  })
}

/** 章节列表：超过 collapseAfter 话就先只铺这些，剩下靠按钮摊开 */
function paintChapters(
  container: HTMLElement,
  data: AlbumDetail,
  resumeChapter: AlbumDetail['chapters'][number] | undefined,
  collapseAfter: number,
): void {
  const listEl = container.querySelector<HTMLElement>('.chapter-list')!
  const moreBtn = container.querySelector<HTMLButtonElement>('.chapter-more')!
  const jumpBtn = container.querySelector<HTMLButtonElement>('.chapter-jump')!

  // 图源偶尔一话都没有，别留个空壳
  if (data.chapters.length === 0) {
    renderEmpty(listEl, { icon: '📄', title: '这部暂时没有章节', hint: '过一会儿再进来看看' })
    return
  }

  const foldable = collapseAfter > 0 && data.chapters.length > collapseAfter
  const lastReadIndex = resumeChapter ? data.chapters.indexOf(resumeChapter) : -1
  let expanded = !foldable

  const paint = (): void => {
    listEl.innerHTML = ''
    for (const ch of expanded ? data.chapters : data.chapters.slice(0, collapseAfter)) {
      const btn = document.createElement('button')
      btn.className = 'chapter-item'
      btn.type = 'button'
      if (ch.photo_id === resumeChapter?.photo_id) btn.classList.add('last-read')
      btn.textContent = ch.title || `第 ${ch.index} 话`   // 图源偶尔给空标题，别留个空白按钮
      btn.addEventListener('click', () => {
        morphToReader(container.querySelector<HTMLElement>('.detail-cover'), `#/read?photo_id=${ch.photo_id}&album_id=${data.id}`)
      })
      listEl.appendChild(btn)
    }

    moreBtn.hidden = !foldable
    moreBtn.textContent = expanded ? '收起' : `展开全部 ${data.chapters.length} 话`

    // 折叠时"上次读到的那话"可能正好被折进去，给个一步跳过去的入口
    const lastReadHidden = foldable && !expanded && lastReadIndex >= collapseAfter
    jumpBtn.hidden = !lastReadHidden
    if (lastReadHidden) jumpBtn.textContent = `跳到上次读到的第 ${lastReadIndex + 1} 话`
  }

  moreBtn.addEventListener('click', () => {
    expanded = !expanded
    paint()
  })

  jumpBtn.addEventListener('click', () => {
    expanded = true
    paint()
    const target = listEl.querySelectorAll<HTMLElement>('.chapter-item')[lastReadIndex]
    target?.scrollIntoView({ block: 'center' })
  })

  paint()
}

/** 右侧评论区：只读预览，先铺 comment_preview 条，点「看更多」再往下加 */
async function paintComments(sideEl: HTMLElement, albumId: string, limit: number): Promise<void> {
  sideEl.innerHTML = `
    <h2 class="side-title">评论<span class="comment-total"></span></h2>
    <div class="comment-list"></div>
    <button type="button" class="comment-more" hidden>看更多</button>
  `
  const listEl = sideEl.querySelector<HTMLElement>('.comment-list')!
  const totalEl = sideEl.querySelector<HTMLElement>('.comment-total')!
  const moreBtn = sideEl.querySelector<HTMLButtonElement>('.comment-more')!

  const items: CommentItem[] = []
  let shown = 0     // 已经铺在页面上的条数
  let page = 0      // 已经取到的页数
  let hasMore = true
  let busy = false

  const paint = (): void => {
    for (const item of items.slice(shown, shown + limit)) {
      listEl.appendChild(commentCard(item))
      shown++
    }
    moreBtn.hidden = shown >= items.length && !hasMore
  }

  const loadNextPage = async (): Promise<void> => {
    const api = window.pywebview?.api
    if (!api) throw new Error('pywebview api 未就绪')
    const data = await api.get_comments(albumId, page + 1)
    page++
    items.push(...data.items)
    hasMore = data.has_more && data.items.length > 0
    totalEl.textContent = data.total ? `（${data.total}）` : ''
  }

  moreBtn.addEventListener('click', () => {
    void (async () => {
      if (busy) return
      busy = true
      try {
        // 这一页还有没铺完的先铺完，铺完了再去要下一页
        if (shown < items.length) paint()
        else {
          await loadNextPage()
          paint()
        }
      } catch (err) {
        listEl.appendChild(hint(`评论加载失败：${String(err)}`))
        moreBtn.hidden = true
      } finally {
        busy = false
      }
    })()
  })

  try {
    await loadNextPage()
    if (items.length === 0) {
      listEl.appendChild(hint('还没有评论'))
      moreBtn.hidden = true
      return
    }
    paint()
  } catch (err) {
    listEl.appendChild(hint(`评论加载失败：${String(err)}`))
    moreBtn.hidden = true
  }
}

/** 一条评论：剧透的先盖住，点一下展开 */
function commentCard(item: CommentItem): HTMLElement {
  const el = document.createElement('article')
  el.className = 'comment'

  const head = document.createElement('div')
  head.className = 'comment-head'
  const user = document.createElement('span')
  user.className = 'comment-user'
  user.textContent = item.nickname
  head.appendChild(user)
  if (item.reply) {
    const tag = document.createElement('span')
    tag.className = 'comment-tag'
    tag.textContent = '回评'
    head.appendChild(tag)
  }
  const date = document.createElement('span')
  date.className = 'comment-date'
  date.textContent = item.created_at
  head.appendChild(date)

  const text = document.createElement('p')
  text.className = 'comment-text'
  text.textContent = item.content

  el.append(head, text)

  if (item.spoiler) {
    el.classList.add('spoiler')
    el.title = '剧透评论，点一下展开'
    el.addEventListener('click', () => el.classList.toggle('revealed'))
  }
  return el
}

function hint(text: string): HTMLElement {
  const el = document.createElement('p')
  el.className = 'comment-hint'
  el.textContent = text
  return el
}

/** 发布日期 / 更新日期：图源没给时是空串或 "0"，这种就别往页面上放 */
function dateLine(data: AlbumDetail): string {
  const parts: string[] = []
  if (isRealDate(data.pub_date)) parts.push(`发布于 ${data.pub_date}`)
  // 更新日期和发布同天就不重复说了
  if (isRealDate(data.update_date) && data.update_date !== data.pub_date) parts.push(`更新于 ${data.update_date}`)
  return parts.join('　')
}

function isRealDate(value: string): boolean {
  return Boolean(value) && value !== '0'
}

function escapeHtml(s: string): string {
  const map: Record<string, string> = {
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }
  return s.replace(/[&<>"']/g, (c) => map[c])
}
