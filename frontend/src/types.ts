export interface Chapter {
  photo_id: string
  index: string
  title: string
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
