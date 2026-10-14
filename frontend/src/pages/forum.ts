// pages/forum.ts
// 论坛：全站评论流（只读，不需要登录）。每条评论下面挂一个"来自本子"的封面条，点它进详情。
import { createIcon, icons } from '../components/icons.js'
import { renderCommentSkeleton, renderEmpty, renderError } from '../components/states.js'
import { onUnmount, pageParam, replaceHash } from '../router.js'
import { waitForApi } from '../webstatus.js'
import type { ForumComment } from '../types.js'

export function forumPage(params: Record<string, string>): HTMLElement {
  const el = document.createElement('div')
  el.className = 'forum-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">论坛</h1>
      <p class="page-sub">全站最新评论，随手翻翻，遇到感兴趣的点封面进本子</p>
    </header>
    <div class="forum-list"></div>
    <button type="button" class="comment-more forum-more" hidden>加载更多</button>
    <p class="comment-hint forum-hint" hidden></p>
  `

  const listEl = el.querySelector<HTMLDivElement>('.forum-list')!
  const moreBtn = el.querySelector<HTMLButtonElement>('.forum-more')!
  const hintEl = el.querySelector<HTMLParagraphElement>('.forum-hint')!

  const startPage = pageParam(params)   // 地址里带的页码（从详情返回 / 刷新）
  let page = 0                 // 已经取到的页数
  let hasMore = true
  let busy = false
  let retries = 0              // 首屏失败自动重来的次数
  let skeletons: HTMLElement[] = []
  let alive = true             // 切走之后晚回来的请求就别碰页面了
  const titles = new Map<string, string>()   // 已经拿到的本子标题
  const asked = new Set<string>()            // 已经问过的本子，别重复问

  onUnmount(() => { alive = false })

  function setHint(text: string): void {
    hintEl.textContent = text
    hintEl.hidden = !text
  }

  /** 等图源的时候铺几行假评论：这条要等十几秒，什么都不铺就像"论坛是空的" */
  function showSkeletons(count: number): void {
    clearSkeletons()
    skeletons = renderCommentSkeleton(listEl, count)
  }

  function clearSkeletons(): void {
    for (const el of skeletons) el.remove()
    skeletons = []
  }

  /** 摊开一页：封面条先拿 JM<id> 顶住，标题下一秒后台补上 */
  function paint(items: ForumComment[]): void {
    const needTitles: string[] = []
    for (const item of items) {
      listEl.appendChild(commentCard(item, titles))
      if (item.album_id && !titles.has(item.album_id) && !asked.has(item.album_id)) {
        asked.add(item.album_id)
        needTitles.push(item.album_id)
      }
    }
    if (needTitles.length > 0) void fillTitles(needTitles)
  }

  /** 标题要额外请求（走详情缓存），回来了就把封面条上的 JM<id> 换掉 */
  async function fillTitles(ids: string[]): Promise<void> {
    const api = window.pywebview?.api
    if (!api) return
    try {
      const got = await api.get_album_titles(ids)
      if (!alive) return
      for (const [aid, title] of Object.entries(got)) titles.set(aid, title)
      for (const chip of listEl.querySelectorAll<HTMLElement>('.forum-album')) {
        const aid = chip.dataset.album
        const title = aid ? titles.get(aid) : undefined
        if (!title) continue
        chip.querySelector<HTMLElement>('.forum-album-title')!.textContent = title
        chip.title = title
      }
    } catch {
      // 标题只是锦上添花，拿不到就继续显示 JM<id>，不打扰用户
    }
  }

  /**
   * 页码写进地址（`#/forum?page=2`）：点进本子详情再返回就落回这一页 ——
   * 跟分类页、搜索页一个路子（replaceState，不往历史里堆）。
   */
  function syncPage(): void {
    const next = page > 1 ? `#/forum?page=${page}` : '#/forum'
    if (window.location.hash !== next) replaceHash(next)
  }

  async function load(): Promise<void> {
    if (busy) return
    const api = window.pywebview?.api
    if (!api) {
      // 桥慢半拍就这样：先提示 + 给个重试按钮，同时盯着桥，就绪了自己接上
      renderError(listEl, 'pywebview api 还没就绪', () => {
        listEl.innerHTML = ''
        void load()
      })
      void waitForApi()
        .then(() => { if (alive && skeletons.length === 0 && page === 0) { listEl.innerHTML = ''; void load() } })
        .catch(() => undefined)
      return
    }
    busy = true
    moreBtn.disabled = true
    moreBtn.textContent = '加载中…'
    setHint('')
    showSkeletons(page === 0 ? 5 : 3)
    try {
      const data = await api.get_forum(page + 1)
      if (!alive) return
      clearSkeletons()
      retries = 0
      page++
      hasMore = data.has_more && data.items.length > 0
      if (data.items.length > 0) syncPage()
      if (page === 1 && data.items.length === 0) {
        renderEmpty(listEl, { icon: '💬', title: '论坛这会儿是空的', hint: '图源没给评论，过一阵再来看看' })
        hasMore = false
        return
      }
      paint(data.items)
    } catch (err) {
      if (!alive) return
      clearSkeletons()
      const message = String(err).replace(/^Error:\s*/, '')
      if (page === 0) {
        // 首屏失败先自己重来两次（图源冷启动爱抖），还不行再让用户点重试
        if (retries < 2) {
          retries++
          hasMore = false   // 自动重试期间"加载更多"先收起来（finally 里会按它设 hidden）
          setHint(`图源没响应，正在重试（第 ${retries} 次）…`)
          window.setTimeout(() => { if (alive) void load() }, 1500 * retries)
          return
        }
        hasMore = false
        renderError(listEl, message, () => {
          listEl.innerHTML = ''
          void load()
        })
      } else {
        // 已经铺出来的别动，底下说一声，用户点「加载更多」还能再来一次
        setHint(`加载失败：${message}`)
      }
    } finally {
      busy = false
      if (alive) {
        moreBtn.textContent = '加载更多'
        moreBtn.disabled = false
        moreBtn.hidden = !hasMore
        if (!hasMore && page > 0) setHint('到底了 —— 服务端只留最新的 5000 条评论')
      }
    }
  }

  moreBtn.addEventListener('click', () => void load())

  // 地址里带了页码就把前面几页顺序补回来（评论分页在后端也有缓存：cache.comment_ttl）
  void (async () => {
    await load()
    while (alive && hasMore && !busy && page < startPage) {
      const before = page
      await load()
      if (page === before) return     // 没进展（失败 / 到底）就别空转
    }
  })()

  return el
}

/** 一条评论：剧透的先盖住，点文字展开 */
function commentCard(item: ForumComment, titles: Map<string, string>): HTMLElement {
  const el = document.createElement('article')
  el.className = 'comment'

  const head = document.createElement('div')
  head.className = 'comment-head'
  const user = document.createElement('span')
  user.className = 'comment-user'
  user.textContent = item.nickname
  head.appendChild(user)
  if (item.reply) head.appendChild(tag('回评'))
  if (item.reply_count > 0) head.appendChild(tag(`${item.reply_count} 回复`))
  const date = document.createElement('span')
  date.className = 'comment-date'
  date.textContent = item.created_at
  head.appendChild(date)

  const text = document.createElement('p')
  text.className = 'comment-text'
  text.textContent = item.content

  el.append(head, text)

  if (item.spoiler) {
    // 监听挂在文字上而不是整张卡：卡里还有个封面按钮，别一戳就把剧透也摊开了
    el.classList.add('spoiler')
    text.title = '剧透评论，点一下展开'
    text.addEventListener('click', () => el.classList.toggle('revealed'))
  }

  if (item.album_id) el.appendChild(albumChip(item, titles))
  return el
}

/** "来自《xxx》"那一条：封面 + 标题（标题没回来之前先显示 JM<id>） */
function albumChip(item: ForumComment, titles: Map<string, string>): HTMLElement {
  const chip = document.createElement('button')
  chip.type = 'button'
  chip.className = 'forum-album'
  chip.dataset.album = item.album_id

  const label = titles.get(item.album_id) || `JM${item.album_id}`
  chip.title = label
  chip.innerHTML = `
    <img class="forum-cover" alt="" loading="lazy" />
    <span class="forum-album-text">
      <span class="forum-album-label">来自</span>
      <span class="forum-album-title"></span>
    </span>
  `
  chip.querySelector<HTMLElement>('.forum-album-title')!.textContent = label

  const img = chip.querySelector<HTMLImageElement>('.forum-cover')!
  if (item.cover_url) {
    img.src = item.cover_url
    img.addEventListener('error', () => img.remove())   // 封面挂了别留个破图标
  } else {
    img.remove()
  }

  // 已收藏的角标：封面才 34px 宽，塞不下「已收藏」三个字，就贴在标题行右端
  if (item.favorited) {
    const badge = document.createElement('span')
    badge.className = 'forum-fav'
    badge.title = '已收藏'
    badge.appendChild(createIcon(icons.heartOn, { size: 12, stroke: 2.2 }))
    const text = document.createElement('span')
    text.textContent = '已收藏'
    badge.appendChild(text)
    chip.appendChild(badge)
  }

  chip.appendChild(createIcon(icons.next, { size: 14 }))
  chip.addEventListener('click', () => {
    window.location.hash = `#/album?id=${item.album_id}`
  })
  return chip
}

function tag(text: string): HTMLElement {
  const el = document.createElement('span')
  el.className = 'comment-tag'
  el.textContent = text
  return el
}
