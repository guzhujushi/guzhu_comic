// pages/detail.ts
import { renderEmpty, renderError } from '../components/states.js'
import type { AlbumDetail, AlbumProgress } from '../types.js'

export function albumPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.className = 'album-detail'

  const albumId = params.id ?? ''
  if (!albumId) {
    renderEmpty(el, {
      icon: '🧭',
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
      const [data, progress] = await Promise.all([
        window.pywebview.api.get_album_detail(albumId),
        // 读不到进度不影响看详情，按"没读过"处理
        window.pywebview.api.get_album_progress(albumId).catch(() => null),
      ])
      renderDetail(data, progress, el)
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

function renderDetail(data: AlbumDetail, progress: AlbumProgress | null, container: HTMLElement): void {
  // 上次读到的那一话还在的话就接着读；列表里找不到（比如图源改了章节）就从第一话开始
  const resumeChapter = progress ? data.chapters.find((c) => c.photo_id === progress.photo_id) : undefined
  const startChapter = resumeChapter ?? data.chapters[0]
  const readLabel = resumeChapter ? `继续阅读 · 第 ${progress!.page_index + 1} 页` : '开始阅读'

  // 封面地址同时喂给虚化层，引号先转义掉，免得把 CSS 里的 url() 拆坏
  const cover = (data.cover_url ?? '').replace(/"/g, '%22')

  container.innerHTML = `
    <button class="back-btn">← 返回</button>
    <div class="detail-hero">
      <img class="detail-cover" src="${cover}" alt="" />
      <h1 class="page-title detail-title">${escapeHtml(data.title)}</h1>
      <p class="detail-meta">作者：${escapeHtml(data.author)}</p>
      <p class="detail-meta">👀 ${escapeHtml(data.views)}　❤️ ${escapeHtml(data.likes)}</p>
      <div class="tags">${data.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>
    </div>
    ${startChapter ? `<button class="read-btn">${readLabel}</button>` : ''}
    <p class="desc">${escapeHtml(data.description)}</p>
    <h2 class="section-title">章节（${data.chapters.length}）</h2>
    <div class="chapter-list"></div>
  `

  // 虚化层用 --cover 当背景，一路渐隐到背景色
  if (cover) container.querySelector<HTMLElement>('.detail-hero')!.style.setProperty('--cover', `url("${cover}")`)

  container.querySelector('.back-btn')!.addEventListener('click', () => history.back())

  // "开始阅读"/"继续阅读"：继续阅读直接跳到上次那一话，页码由阅读器自己恢复
  container.querySelector('.read-btn')?.addEventListener('click', () => {
    window.location.hash = `#/read?photo_id=${startChapter.photo_id}&album_id=${data.id}`
  })

  const listEl = container.querySelector<HTMLElement>('.chapter-list')!

  // 图源偶尔一话都没有，别留个空壳
  if (!startChapter) {
    renderEmpty(listEl, { icon: '📄', title: '这部暂时没有章节', hint: '过一会儿再进来看看' })
    return
  }
  for (const ch of data.chapters) {
    const btn = document.createElement('button')
    btn.className = 'chapter-item'
    if (resumeChapter && ch.photo_id === resumeChapter.photo_id) btn.classList.add('last-read')
    btn.textContent = ch.title || `第 ${ch.index} 话`   // 图源偶尔给空标题，别留个空白按钮
    btn.addEventListener('click', () => {
      window.location.hash = `#/read?photo_id=${ch.photo_id}&album_id=${data.id}`
    })
    listEl.appendChild(btn)
  }
}

function escapeHtml(s: string): string {
  const map: Record<string, string> = {
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }
  return s.replace(/[&<>"']/g, (c) => map[c])
}