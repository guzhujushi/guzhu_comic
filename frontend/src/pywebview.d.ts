interface AlbumSummary {
  id: string
  title: string
  cover_url?: string
}

type RankRange = "day" | "week" | "month"

interface PyApi {
  search(keyword: string): Promise<AlbumSummary[]>
  get_ranking(time_range: str, page?: number): Promis<AlbumSummary[]>
}

interface PyWebview {
  api: PyApi
}

interface Window {
  pywebview?: PyWebview
}