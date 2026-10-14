// pages/category.ts
import { boardPage, CATEGORY_KEYS } from './board.js'
import { pageParam } from '../router.js'
import { pickKey } from '../store.js'

/**
 * 分类页：#/category?c=doujin —— 从首页标签条或者某一行的「更多」跳过来。
 * 跟首页同一套版式：hero 换成这个分类最火的三部，面板换成它的整页列表。
 */
export function categoryPage(params: Record<string, string>): HTMLElement {
  return boardPage(pickKey(params.c, CATEGORY_KEYS, 'all'), pageParam(params))
}
