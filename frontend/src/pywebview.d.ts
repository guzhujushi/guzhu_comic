interface AlbumSummary {
  id: string
  title: string
  cover_url?: string
  subtitle?: string
  /** 在本地收藏里吗：列表接口返回前现拼（不进缓存），界面靠它打「已收藏」角标 */
  favorited?: boolean
}

/** 推荐段的一条：subtitle 是"为什么推它"（命中的 tag / 作者） */
interface Recommendation {
  id: string
  title: string
  cover_url: string
  subtitle: string
  favorited: boolean
  score: number
}

/** 一批推荐：cold = 画像空或者一个都没命中，界面该写「热门推荐」 */
interface RecommendPage {
  cold: boolean
  items: Recommendation[]
}

/** 一条搜索记录（存在 data/app.db 的 search_log） */
interface SearchLogItem {
  keyword: string
  scope: SearchScope
  hits: number
  at: number
}

interface AlbumProgress {
  photo_id: string
  page_index: number
  title: string
}

/** 一次整本下载任务（data/app.db 的 download_album + download_chapter） */
interface DownloadTask {
  album_id: string
  title: string
  cover_url: string
  /** queued / running / paused / done / error */
  state: string
  error: string
  /** 总话数 / 已下完的话数 */
  total: number
  done: number
  /** 已下 / 待下 的张数（话单里的图，总量随话推进才知道） */
  images_done: number
  images_total: number
  added_at: number
  updated_at: number
  /** 有没有在跑（queued / running）：下载页靠它决定要不要轮询 */
  running: boolean
  /** 阅读进度：跟「最近阅读」同一个口径（同一张 history 表），没读过是 null */
  read: AlbumProgress | null
}

interface FavoriteItem {
  album_id: string
  title: string
  cover_url: string
  added_at: number
  favorited?: boolean
}

type RankRange = "day" | "week" | "month"
type ComicCategory = "all" | "doujin" | "single" | "short" | "hanman" | "meiman";
type SearchScope = "site" | "work" | "author" | "tag" | "actor";
type SortOrder = "latest" | "views" | "likes" | "score" | "images" | "comments";

interface PyApi {
  search(keyword: string, page?: number, scope?: SearchScope, order_by?: SortOrder): Promise<AlbumSummary[]>
  get_ranking(time_range: RankRange, category?: ComicCategory, page?: number, order_by?: SortOrder): Promise<AlbumSummary[]>
  clear_cache(): Promise<{ meta_rows: number; cache_files: number }>
  get_cache_stats(): Promise<{ used_mb: number; limit_mb: number; interval: number; chapters: number }>
  cleanup_cache(): Promise<{ used_mb: number; removed_chapters: number; freed_mb: number }>
  get_album_detail(album_id: string): Promise<AlbumDetail>
  get_chapter(photo_id: string): Promise<ChapterImages>
  get_comments(album_id: string, page?: number): Promise<CommentPage>
  get_forum(page?: number): Promise<ForumPage>
  get_recommendations(kind?: "home" | "search", limit?: number, exclude?: string[]): Promise<RecommendPage>
  get_taste_profile(): Promise<{
    tags: { tag: string; weight: number }[]
    authors: { author: string; weight: number }[]
    favorites: number
    searches: number
  }>
  log_search(keyword: string, scope?: SearchScope): Promise<void>
  get_search_log(limit?: number): Promise<SearchLogItem[]>
  remove_search_log(keyword: string): Promise<void>
  clear_search_log(): Promise<void>
  get_album_titles(album_ids: string[]): Promise<Record<string, string>>
  prefetch_albums(album_ids: string[]): Promise<number>
  prefetch_chapter(photo_id: string): Promise<number>
  prefetch_home(time_range: string, order_by?: string): Promise<number>
  is_favorite(album_id: string): Promise<boolean>
  toggle_favorite(album_id: string, title?: string, cover_url?: string, tags?: string[], authors?: string[]): Promise<boolean>
  remove_favorite(album_id: string): Promise<void>
  get_favorites(limit?: number, offset?: number): Promise<FavoriteItem[]>
  start_download(album_id: string, title?: string, cover_url?: string, chapters?: { photo_id: string; index: string; title: string }[]): Promise<DownloadTask | null>
  get_downloads(): Promise<DownloadTask[]>
  get_download(album_id: string): Promise<DownloadTask | null>
  pause_download(album_id: string): Promise<DownloadTask | null>
  resume_download(album_id: string): Promise<DownloadTask | null>
  remove_download(album_id: string, delete_files?: boolean): Promise<{ removed: boolean; files: number }>
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