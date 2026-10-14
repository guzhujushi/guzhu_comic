// 顺手预热：列表铺完拉详情缓存、详情页 / 阅读时下「开头几张」章节图。
// 全是后台慢慢来的活 —— 失败、桥没就绪、后端没这个方法都直接咽掉，别影响界面上任何东西。
// 条数 / 张数上限在后端读（config.yaml 的 prefetch 组），前端只负责说「这些在屏幕上」。

/** 列表（首页 / 搜索）铺出来之后，把这几个本子的详情缓存预热掉（详情里有 tag，留给以后推荐用） */
export function warmAlbumList(ids: string[]): void {
  const api = window.pywebview?.api
  if (!api?.prefetch_albums || ids.length === 0) return
  void api.prefetch_albums(ids).catch(() => undefined)
}

/** 把这一话开头几张先下下来：进详情页预热要读的那一话，阅读到后段预热下一话 */
export function warmChapterStart(photoId: string): void {
  const api = window.pywebview?.api
  if (!api?.prefetch_chapter || !photoId) return
  void api.prefetch_chapter(photoId).catch(() => undefined)
}
