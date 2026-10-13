// pages/album.ts
import type { AlbumDetail, AlbumProgress } from '../types.js'

export function albumPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.className = 'album-detail'

  const albumId = params.id ?? ''
  if (!albumId) {
    el.innerHTML = '<p class="empty-hint">缺少漫画 ID</p>'
    return el
  }

  el.innerHTML = '<p class="empty-hint">加载中...</p>'

  void (async () => {
    if (!window.pywebview?.api) {
      el.innerHTML = '<p class="empty-hint">pywebview api 未就绪</p>'
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
      el.innerHTML = `<p class="empty-hint">加载失败: ${String(err)}</p>`
    }
  })()

  return el
}

function renderDetail(data: AlbumDetail, progress: AlbumProgress | null, container: HTMLElement): void {
  // 上次读到的那一话还在的话就接着读；列表里找不到（比如图源改了章节）就从第一话开始
  const resumeChapter = progress ? data.chapters.find((c) => c.photo_id === progress.photo_id) : undefined
  const startChapter = resumeChapter ?? data.chapters[0]
  const readLabel = resumeChapter ? `继续阅读 · 第 ${progress!.page_index + 1} 页` : '开始阅读'

  container.innerHTML = `
    <button class="back-btn">← 返回</button>
    <div class="detail-head">
      <img src="${data.cover_url}" alt="" />
      <div class="detail-info">
        <h2>${escapeHtml(data.title)}</h2>
        <p>作者：${escapeHtml(data.author)}</p>
        <p>👀 ${escapeHtml(data.views)}　❤️ ${escapeHtml(data.likes)}</p>
        <div class="tags">${data.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>
      </div>
    </div>
    <p class="desc">${escapeHtml(data.description)}</p>
    ${startChapter ? `<button class="read-btn">${readLabel}</button>` : ''}
    <h3>章节（${data.chapters.length}）</h3>
    <div class="chapter-list"></div>
  `
  container.querySelector('.back-btn')!.addEventListener('click', () => history.back())

  // "开始阅读"/"继续阅读"：继续阅读直接跳到上次那一话，页码由阅读器自己恢复
  container.querySelector('.read-btn')?.addEventListener('click', () => {
    window.location.hash = `#/read?photo_id=${startChapter.photo_id}&album_id=${data.id}`
  })

  const listEl = container.querySelector('.chapter-list')!
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
