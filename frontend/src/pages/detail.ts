// pages/album.ts
import type { AlbumDetail } from '../types.js'

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
      const data = await window.pywebview.api.get_album_detail(albumId)
      renderDetail(data, el)
    } catch (err) {
      el.innerHTML = `<p class="empty-hint">加载失败: ${String(err)}</p>`
    }
  })()

  return el
}

function renderDetail(data: AlbumDetail, container: HTMLElement): void {
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
    <h3>章节（${data.chapters.length}）</h3>
    <div class="chapter-list"></div>
  `
  container.querySelector('.back-btn')!.addEventListener('click', () => history.back())

  const listEl = container.querySelector('.chapter-list')!
  for (const ch of data.chapters) {
    const btn = document.createElement('button')
    btn.className = 'chapter-item'
    btn.textContent = ch.title
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
