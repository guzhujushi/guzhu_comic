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
  /** 卡片下面那行小字，比如"读到第 61 页" */
  subtitle?: string
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
