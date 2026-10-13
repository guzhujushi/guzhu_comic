interface AlbumSummary {
  id: string
  title: string
  cover_url?: string
  subtitle?: string
}

interface AlbumProgress {
  photo_id: string
  page_index: number
  title: string
}

type RankRange = "day" | "week" | "month"
type ComicCategory = "all" | "doujin" | "single" | "short" | "hanman" | "meiman";

interface PyApi {
  search(keyword: string): Promise<AlbumSummary[]>
  get_ranking(time_range: RankRange, category?: ComicCategory, page?: number): Promise<AlbumSummary[]>
  clear_cache(): Promise<{ meta_rows: number; cache_files: number }>
  get_cache_stats(): Promise<{ used_mb: number; limit_mb: number; interval: number; chapters: number }>
  cleanup_cache(): Promise<{ used_mb: number; removed_chapters: number; freed_mb: number }>
  get_album_detail(album_id: string): Promise<AlbumDetail>
  get_chapter(photo_id: string): Promise<ChapterImages>
  save_progress(album_id: string, photo_id: string, page_index: number, title?: string, cover_url?: string): Promise<void>
  get_progress(album_id: string, photo_id: string): Promise<number>
  get_history(limit?: number): Promise<HistoryItem[]>
  get_album_progress(album_id: string): Promise<AlbumProgress | null>
  get_settings(): Promise<Record<string, any>>
  save_settings(settings: Record<string, any>): Promise<Record<string, any>>
}

interface PyWebview {
  api: PyApi
}

interface Window {
  pywebview?: PyWebview
}