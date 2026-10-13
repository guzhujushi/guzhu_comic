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