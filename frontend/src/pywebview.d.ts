interface AlbumSummary {
  id: string
  title: string
}

interface PyApi {
  search(keyword: string): Promise<AlbumSummary[]>
}

interface PyWebview {
  api: PyApi
}

interface Window {
  pywebview?: PyWebview
}