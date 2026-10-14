// resume.ts
import { createIcon, icons } from './components/icons.js'
import { bridgeCall } from './webstatus.js'
import type { HistoryItem } from './types.js'

/** 封面取不到时的兜底（跟空状态、闪屏用的是同一张头像图） */
const FALLBACK_COVER = '/apple-touch-icon.png'

/**
 * 左下角的「继续阅读」：上面一张卡（封面 + 标题 + 读到第几页），下面一个按钮，
 * 两个都指向「最近阅读」里时间最近的那一条 —— 点了直接进阅读器，接着上次那一页看。
 *
 * 为什么塞进导航：读漫画八成是「接着上次」，把它摆在每次都要经过的地方，比让人先点
 * 「最近阅读」再找那一条少两步。没读过任何一话就整块 `hidden`，不留空位。
 *
 * 这里**不走** `morphToReader`（封面飞进阅读器那套）：导航是常驻的，进阅读器时
 * `body.reading` 会把 `#nav` 整个 `display:none`，源元素会在转场中途消失 —— 快照
 * 对不上，不如老老实实换个 hash。
 */
export function createResume(): { el: HTMLElement; refresh: () => Promise<void> } {
  const el = document.createElement('div')
  el.className = 'nav-resume'
  el.hidden = true
  el.innerHTML = `
    <a class="resume-card" href="#/popular">
      <img class="resume-cover" src="${FALLBACK_COVER}" alt="" />
      <span class="resume-text">
        <span class="resume-title"></span>
        <span class="resume-sub"></span>
      </span>
    </a>
    <button type="button" class="nav-resume-go"><span>继续阅读</span></button>
  `

  const card = el.querySelector<HTMLAnchorElement>('.resume-card')!
  const cover = el.querySelector<HTMLImageElement>('.resume-cover')!
  const titleEl = el.querySelector<HTMLElement>('.resume-title')!
  const subEl = el.querySelector<HTMLElement>('.resume-sub')!
  const goBtn = el.querySelector<HTMLButtonElement>('.nav-resume-go')!
  goBtn.prepend(createIcon(icons.play, { size: 16 }))

  // 封面挂了就退回占位图；只换一次，别让 onerror 自己咬自己
  cover.addEventListener('error', () => {
    if (!cover.src.endsWith(FALLBACK_COVER)) cover.src = FALLBACK_COVER
  })

  let current: HistoryItem | null = null
  // 卡片和按钮都跳这一个 hash。**不能读 `card.href`** —— 那是解析后的绝对地址
  // （`http://…/#/read?…`），拿去当 hash 会变成 `ttp://…` 那种垃圾
  let target = '#/popular'
  let loading = false
  // 一次都没跟后端对上话之前，自己再来几次：桥是「两步注入」的（见 webstatus.ts），
  // 方法有可能还没挂上，那时候静默返回 = 这张卡这一趟永远不出现。
  let settled = false
  let retries = 0
  let retryTimer = 0
  const RETRY_LIMIT = 6

  /**
   * 还没跟后端对上话就过 1.5 秒再来一次（最多 6 次，约 9 秒）。
   * 一旦拿到过一次结果（有历史铺出卡 / 确实没历史）就不再自疗 —— 它是常驻导航上的一块，
   * 在那儿反复空转没意义。
   */
  function retryLater(): void {
    if (settled || retryTimer !== 0 || retries >= RETRY_LIMIT) return
    retries += 1
    retryTimer = window.setTimeout(() => {
      retryTimer = 0
      void refresh()
    }, 1500)
  }

  function paint(item: HistoryItem | null): void {
    current = item
    el.hidden = !item
    if (!item) return
    const name = item.title || `漫画 ${item.album_id}`
    target = `#/read?photo_id=${item.photo_id}&album_id=${item.album_id}`
    card.setAttribute('href', target)
    titleEl.textContent = name
    subEl.textContent = `读到第 ${item.page_index + 1} 页`
    // 窄屏（rail 64px）会把卡片藏起来、按钮只剩图标，标题只能挂在 title 上
    card.title = `继续阅读《${name}》`
    goBtn.title = card.title
    goBtn.setAttribute('aria-label', card.title)
    if (!cover.src.endsWith(item.cover_url || FALLBACK_COVER)) cover.src = item.cover_url || FALLBACK_COVER
  }

  goBtn.addEventListener('click', () => {
    if (current) window.location.hash = target
  })

  /**
   * 拉一次「最近阅读」的第一条。导航里不报错：拿不到就当没有（这块是锦上添花，
   * 不能因为一次 sqlite 抖动让左下角挂个红字）。同时只跑一次 —— hashchange 会在
   * 连着翻页时排成一队，没必要都发出去。
   *
   * 拿不到（桥重注入把回调清掉 / 桥还没挂上 / 后端抖一下）就交给 retryLater 自己再试几次：
   * 这张卡是「一次判死」的重灾区 —— 首趟没铺上，后面就再没人叫它了，用户只看到左下角空着。
   * 走 bridgeCall 还有个好处：被清掉的调用会**当场**抛出来（不是永远挂着），loading 不会卡死。
   */
  async function refresh(): Promise<void> {
    if (loading) return
    loading = true
    try {
      const rows = await bridgeCall('get_history', [1], 2)
      paint(rows?.[0] ?? null)
      settled = true
      window.clearTimeout(retryTimer)
      retryTimer = 0
    } catch {
      // 读不到就先留着上一次的（比突然消失好）；一次都没成功过的话过会儿再试
      retryLater()
    } finally {
      loading = false
    }
  }

  return { el, refresh }
}