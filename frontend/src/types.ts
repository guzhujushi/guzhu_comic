export interface Chapter {
  photo_id: string
  index: string
  title: string
}

/** 相关作品：详情页里"顺藤摸瓜"的那排卡片 */
export interface RelatedAlbum {
  id: string
  title: string
  author: string
  cover_url: string
}

export interface AlbumDetail {
  id: string
  title: string
  author: string
  authors: string[]
  description: string
  tags: string[]
  likes: string
  views: string
  page_count: number
  cover_url: string
  comment_count: string
  pub_date: string
  update_date: string
  related: RelatedAlbum[]
  chapters: Chapter[]
}

export interface AlbumSummary {
  id: string
  title: string
  cover_url?: string
  /** 卡片下面那行小字，比如"读到第 61 页"、推荐卡的命中原因 */
  subtitle?: string
  /** 在本地收藏里吗（列表接口现拼）：只有 true 才打「已收藏」角标，没收藏什么都不加 */
  favorited?: boolean
}

/** 推荐段的一条：subtitle 是"为什么推它"（命中的 tag / 作者） */
export interface Recommendation {
  id: string
  title: string
  cover_url: string
  subtitle: string
  favorited: boolean
  score: number
}

/** 一批推荐：cold = 画像空或者一个都没命中，标题该写「热门推荐」而不是「为你推荐」 */
export interface RecommendPage {
  cold: boolean
  items: Recommendation[]
}

/** 一条搜索记录（data/app.db 的 search_log）：后端拿它当推荐画像的输入 */
export interface SearchLogItem {
  keyword: string
  scope: SearchScope
  hits: number
  at: number
}

export interface ChapterImages {
  photo_id: string
  images: string[]
}

export interface HistoryItem {
  album_id: string
  photo_id: string
  page_index: number
  title: string
  cover_url: string
  updated_at: number
}

/** 某部漫画最近读到哪一话哪一页（详情页判断"开始阅读"/"继续阅读"用） */
export interface AlbumProgress {
  photo_id: string
  page_index: number
  title: string
}

/** 一条评论：只读预览，剧透的默认用 CSS 盖住 */
export interface CommentItem {
  nickname: string
  content: string
  created_at: string
  spoiler: boolean
  reply: boolean
}

export interface CommentPage {
  total: number
  has_more: boolean
  items: CommentItem[]
}

/** 论坛（全站评论流）里的一条：album_id 为空串表示这条评论没挂本子 */
export interface ForumComment {
  comment_id: string
  nickname: string
  content: string
  created_at: string
  spoiler: boolean
  reply: boolean
  reply_count: number
  album_id: string
  cover_url: string
  /** 这条评论挂的本子已经在收藏里吗（界面给封面条打「已收藏」） */
  favorited: boolean
}

export interface ForumPage {
  total: number
  has_more: boolean
  items: ForumComment[]
}

/** 本地收藏的一条：封面地址是加收藏那一刻存的快照，图源换线路后可能失效 */
export interface FavoriteItem {
  album_id: string
  title: string
  cover_url: string
  added_at: number
}
