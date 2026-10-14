// 推荐段：首页面板里第一段、搜索页结果下面那一段，两处共用这一套。
// 一期两个位置的结果完全一致（搜索页不吃本次关键词，用户 2026-10-14 定的口径）。
// 铺不出来 —— 慢、失败、配置里关掉 —— 就把整段藏起来，绝不连累页面上别的东西。
import { renderAlbumList } from './album-list.js'
import { createIcon, icons } from './icons.js'
import { renderAlbumSkeleton } from './states.js'
import { warmAlbumList } from '../prefetch.js'
import { bridgeCall } from '../webstatus.js'
import type { AlbumSummary, RecommendPage, Recommendation } from '../types.js'

export interface RecommendSection {
  /** 挂到页面上的那一段（没数据 / 失败时 hidden） */
  el: HTMLElement
  /** 首次铺一次；重复调用什么都不做（换榜单 / 换排序不用重推） */
  load(): void
}

/**
 * `shownAbove`（可选）：页面上方已经展示过的 ID（首页就是 hero 那几部）—— 这一段不再给这些，
 * 免得同一部书上下各出现一次。
 *
 * **首页要等 hero 请求回来之后再调 `load()`**（见 `board.ts`）：早调的话这里拿到的是空名单，
 * 去重就落空了。候选池是在**打分之前**就把这些剔掉的（`get_recommendations` 的 `exclude`），
 * 所以剔掉几部不影响这一段铺满一行。
 */
export function createRecommendSection(
  kind: 'home' | 'search', shownAbove?: () => string[],
): RecommendSection {
  const el = document.createElement('section')
  el.className = 'cat-section rec-section'
  el.hidden = true

  const head = document.createElement('div')
  head.className = 'cat-head'
  const name = document.createElement('h2')
  name.className = 'cat-name rec-name'
  name.textContent = '为你推荐'
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'cat-more rec-refresh'
  btn.textContent = '换一批'
  btn.appendChild(createIcon(icons.next, { size: 14 }))
  head.append(name, btn)

  // 首页那一段跟分类横条一样一行 --cols 张（吃面板上的 --cols）；
  // 搜索页没有面板尺寸那套，就交给 .album-list 自己的 auto-fill
  const row = document.createElement('div')
  row.className = kind === 'home' ? 'album-list cat-row rec-row' : 'album-list rec-row'
  el.append(head, row)

  const shown: string[] = []      // 这一段已经给过哪些 ID（「换一批」时排除掉）
  let started = false
  let busy = false
  let painted = 0
  let exhausted = false           // 候选被「换一批」翻完了
  let retries = 0
  let retryTimer = 0

  /**
   * **没铺出东西**时自动再来几次（最多 3 次，退避 0.9 / 1.8 / 2.7 秒）。
   *
   * 三种"其实还来得及"的情况：① 桥是两步注入的，方法可能还没挂上（见 webstatus.ts）；
   * ② 后端推荐只读本地的榜单缓存、**自己不额外发请求**，首页刚开时榜单可能还没落缓存
   * （候选池空 = 这一次给不出东西）；③ 后端抖一下。
   * 这三种以前都是一次判死、`hidden` 到用户切页为止 —— "第一次进首页没有推荐段"就是这么来的。
   * 重试期间骨架留在原地（那本来就是"马上就来"的意思），三次都空才把整段藏掉。
   */
  function retryLater(): void {
    if (retries >= 3) {
      if (painted === 0) el.hidden = true
      return
    }
    retries++
    window.clearTimeout(retryTimer)
    retryTimer = window.setTimeout(() => {
      retryTimer = 0
      if (document.contains(el)) void fill()   // 页面已经切走了就别再打桥
    }, 900 * retries)
  }

  function toCard(item: Recommendation): AlbumSummary {
    return {
      id: item.id,
      title: item.title,
      cover_url: item.cover_url,
      subtitle: item.subtitle,
      favorited: item.favorited,
    }
  }

  async function fill(): Promise<void> {
    if (busy) return
    busy = true
    btn.disabled = true
    if (painted === 0) {
      // 先把骨架摆上：它在首页是第一段，别等结果回来才把下面几行往下挤
      el.hidden = false
      renderAlbumSkeleton(row, kind === 'home' ? 5 : 6)
    }
    try {
      const exclude = shownAbove ? [...shown, ...shownAbove()] : shown
      const page: RecommendPage = await bridgeCall('get_recommendations', [kind, undefined, exclude])
      const items = page?.items ?? []
      if (items.length === 0) {
        if (painted === 0) retryLater()       // 候选池还冷：留着骨架再试，三次都空才藏
        else exhausted = true                 // 候选翻完了：按钮留着但点不动
        return
      }
      name.textContent = page.cold ? '热门推荐' : '为你推荐'
      for (const item of items) shown.push(item.id)
      painted += items.length
      el.hidden = false
      renderAlbumList(items.map(toCard), row)
      // 封面 + 标题已经铺上，详情缓存丢后台慢慢预热（推荐打分要的就是详情里的 tag）
      warmAlbumList(items.map((item) => item.id))
    } catch {
      // 推荐挂了不报错、不连累页面：没铺出来就整段不出现（先自己重试几次再说）
      if (painted === 0) retryLater()
    } finally {
      busy = false
      btn.disabled = exhausted
    }
  }

  btn.addEventListener('click', () => void fill())

  return {
    el,
    load() {
      if (started) return
      started = true
      void fill()
    },
  }
}
