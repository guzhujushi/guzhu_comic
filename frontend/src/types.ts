interface Chapter {
  photo_id: string
  index: string
  title: string
}

interface AlbumDetail {
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
