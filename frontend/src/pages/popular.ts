// pages/popular.ts
import { boardPage } from './board.js'

/** 首页 = 榜单板的「全部」那一页：hero 是全部最火的三部，下面铺别的分类各一行 */
export function popularPage(): HTMLElement {
  return boardPage('all')
}
