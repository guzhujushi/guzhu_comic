interface AlbumSummary {
  id: string
  title: string
  cover_url?: string
}

type RankRange = "day" | "week" | "month"
type ComicCategory = "all" | "doujin" | "single" | "short" | "hanman" | "meiman";

interface PyApi {
  search(keyword: string): Promise<AlbumSummary[]>
  get_ranking(time_range: RankRange, category?: ComicCategory, page?: number): Promis<AlbumSummary[]>
  clear_cache(): Promise<{ meta_rows: number; cover_files: number }>
  get_album_detail(album_id: string): Promise<AlbumDetail>
  get_chapter(photo_id: string): Promise<ChapterImages>
}

interface PyWebview {
  api: PyApi
}

interface Window {
  pywebview?: PyWebview
}