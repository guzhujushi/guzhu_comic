// pages/downloads.ts
import { AlbumCard } from '../components/album.js'
import { createIcon, icons, morphIcon } from '../components/icons.js'
import { renderAlbumSkeleton, renderEmpty, renderError } from '../components/states.js'
import { onUnmount } from '../router.js'
import type { DownloadTask } from '../types.js'

/** 刷新时只改文字的那几个节点：整块重建 DOM 会把鼠标悬停和下一次点击都打断 */
interface Cell {
  book: AlbumCard
  badge: HTMLElement
  toggle: HTMLButtonElement
  toggleIcon: HTMLElement
  toggleText: HTMLElement
  /** 上次画的是不是"该显示继续"（图标只在它翻转时才变形一次） */
  paused: boolean
}

/**
 * 我的下载：任务表在 data/app.db，离线副本在 config.yaml 的 download.dir 里。
 * 副标题里的"读到第 N 页"跟「最近阅读」同一个口径 —— 后端把 history 那行现拼在 read 上。
 */
export function downloadsPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'downloads-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">我的下载</h1>
      <p class="page-sub">存在本机的离线副本，清缓存、断网都能看；没下完的会接着下</p>
    </header>
    <p class="dl-error" hidden></p>
    <div class="album-list"></div>
  `

  const listEl = el.querySelector<HTMLDivElement>('.album-list')!
  const errorEl = el.querySelector<HTMLParagraphElement>('.dl-error')!
  const cells = new Map<string, Cell>()
  let tasks: DownloadTask[] = []
  // 必须拿 null 起手：空列表算出来的 ids 就是 ''，起手写 '' 的话第一次 sync() 会以为
  // "这一屏已经画过了"，于是永远不去铺空态 —— 一次都没下过的用户就盯着 4 张骨架卡片看它闪
  let renderedIds: string | null = null
  let timer = 0

  function showError(message: string): void {
    errorEl.textContent = message
    errorEl.hidden = !message
  }

  const clean = (err: unknown): string => String(err).replace(/^Error:\s*/, '')

  /** 话数进度那一句 */
  function progressLine(task: DownloadTask): string {
    const held = `${task.done}/${task.total} 话`
    if (task.state === 'done') return `已下载 ${task.total} 话`
    if (task.state === 'paused') return `已暂停（${held}）`
    if (task.state === 'error') return `下到 ${held}，还有没下完的`
    return `下载中 ${held}`
  }

  function subtitle(task: DownloadTask): string {
    const read = task.read ? `读到第 ${task.read.page_index + 1} 页` : ''
    return read ? `${progressLine(task)} · ${read}` : progressLine(task)
  }

  function badgeText(task: DownloadTask): string {
    if (task.state === 'paused') return '已暂停'
    if (task.state === 'error') return '没下完'
    const pct = task.total ? Math.round((task.done / task.total) * 100) : 0
    return `下载中 ${pct}%`
  }

  /** 只在文字 / 状态上改：卡片尺寸和封面都不动，鼠标不会因为刷新跳走 */
  function paintCell(task: DownloadTask): void {
    const cell = cells.get(task.album_id)
    if (!cell) return
    cell.book.setData({
      id: task.album_id,
      title: task.title || `漫画 ${task.album_id}`,
      cover_url: task.cover_url || undefined,
      subtitle: subtitle(task),
    })
    const showBadge = task.state !== 'done'      // 下完的卡片不再挂角标，页面才不吵
    cell.badge.hidden = !showBadge
    if (showBadge) cell.badge.textContent = badgeText(task)
    const paused = !task.running
    if (paused !== cell.paused) {
      cell.paused = paused
      morphIcon(cell.toggleIcon, paused ? icons.play : icons.pause)
    }
    cell.toggleText.textContent = paused ? '继续' : '暂停'
    cell.toggle.title = paused ? '接着下（只补缺的部分）' : '暂停（已经下好的都留着）'
  }

  function build(task: DownloadTask): HTMLElement {
    const cell = document.createElement('div')
    cell.className = 'dl-cell'

    const book = new AlbumCard()
    book.classList.add('dl-book')
    book.addEventListener('click', () => {
      window.location.hash = `#/album?id=${task.album_id}`
    })

    const badge = document.createElement('span')
    badge.className = 'dl-badge'
    book.append(badge)

    const actions = document.createElement('div')
    actions.className = 'dl-actions'

    const paused = !task.running
    const toggle = document.createElement('button')
    toggle.type = 'button'
    toggle.className = 'dl-btn dl-toggle'
    const toggleIcon = createIcon(paused ? icons.play : icons.pause, { size: 13 })
    const toggleText = document.createElement('span')
    toggle.append(toggleIcon, toggleText)
    toggle.addEventListener('click', (ev) => {
      ev.stopPropagation()     // 别冒泡成"进详情"
      void repaintAfter(toggleTask(task))
    })

    const del = document.createElement('button')
    del.type = 'button'
    del.className = 'dl-btn dl-del'
    del.title = '删除下载，离线副本一起删'
    del.setAttribute('aria-label', `删除 ${task.title || task.album_id} 的下载`)
    const delText = document.createElement('span')
    delText.textContent = '删除'
    del.append(createIcon(icons.trash, { size: 13 }), delText)
    del.addEventListener('click', (ev) => {
      ev.stopPropagation()
      void removeTask(task)
    })

    actions.append(toggle, del)
    cell.append(book, actions)
    cells.set(task.album_id, { book, badge, toggle, toggleIcon, toggleText, paused })
    paintCell(task)
    return cell
  }

  function paint(): void {
    listEl.innerHTML = ''
    cells.clear()
    if (tasks.length === 0) {
      renderEmpty(listEl, {
        avatar: true,
        title: '还没有下载',
        hint: '在详情页点「下载」，整本存到本机，断网也能看',
        actionLabel: '去热门',
        onAction: () => { window.location.hash = '#/popular' },
      })
      return
    }
    for (const task of tasks) listEl.appendChild(build(task))
  }

  /** 任务集合变了才重建卡片，否则只改文字（轮询每秒都在跑，别把 DOM 拆了重建） */
  function sync(): void {
    const ids = tasks.map((task) => task.album_id).join(',')
    if (ids !== renderedIds) {
      renderedIds = ids
      paint()
      return
    }
    for (const task of tasks) paintCell(task)
  }

  function replace(task: DownloadTask): void {
    tasks = tasks.map((it) => (it.album_id === task.album_id ? task : it))
    sync()
    schedule()
  }

  function stopPoll(): void {
    if (timer) {
      window.clearInterval(timer)
      timer = 0
    }
  }

  /** 有任务在跑才轮询：都下完了就别每 1.5 秒问一次后端 */
  function schedule(): void {
    stopPoll()
    if (!tasks.some((task) => task.running)) return
    timer = window.setInterval(() => void refresh(), 1500)
  }

  onUnmount(stopPoll)

  async function refresh(): Promise<void> {
    const api = window.pywebview?.api
    if (!api?.get_downloads) return
    try {
      const next = await api.get_downloads()
      // 这份必须是数组（下面还要 some / map）；形状不对就当空列表，别在这儿抛出一个
      // 没人接的 rejection，把整页停在骨架上
      tasks = Array.isArray(next) ? next : []
      showError('')
      sync()
    } catch (err) {
      showError(`下载列表读不出来：${clean(err)}`)
    }
    schedule()
  }

  async function toggleTask(task: DownloadTask): Promise<DownloadTask | null> {
    const api = window.pywebview?.api
    if (!api) return null
    try {
      const next = task.running
        ? await api.pause_download(task.album_id)
        : await api.resume_download(task.album_id)
      showError('')
      return next
    } catch (err) {
      showError(`操作失败：${clean(err)}`)
      return null
    }
  }

  /** 按钮点完的收尾：拿回来的新状态直接铺上，别再等一次轮询 */
  async function repaintAfter(pending: Promise<DownloadTask | null>): Promise<void> {
    const next = await pending
    if (next) replace(next)
    else if (window.pywebview?.api) await refresh()
  }

  async function removeTask(task: DownloadTask): Promise<void> {
    const api = window.pywebview?.api
    if (!api) return
    try {
      await api.remove_download(task.album_id, true)
      showError('')
      tasks = tasks.filter((it) => it.album_id !== task.album_id)
      sync()
      schedule()
    } catch (err) {
      showError(`删除失败：${clean(err)}`)
    }
  }

  async function load(): Promise<void> {
    if (!window.pywebview?.api) {
      renderError(listEl, 'pywebview api 还没就绪', () => void load())
      return
    }
    renderAlbumSkeleton(listEl, 4)
    await refresh()
  }

  void load()

  return el
}
