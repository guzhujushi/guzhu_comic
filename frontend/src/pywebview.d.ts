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
  /** 这次会话已经下下来多少字节（只算本次会话新下的，不是磁盘上那份的总和） */
  bytes_done: number
  /** 每秒字节数；刚开跑或停了就是 0 */
  speed_bps: number
  /** 还要多少秒（估算，按"平均一张图多大 × 还剩几张"算）；算不出来是 null */
  eta_s: number | null
}

/** 版本信息：app = 安装包（exe），web = 当前这份前端（空串 = 出厂那份） */
interface VersionInfo {
  app: string
  web: string
  built_in: string
  frozen: boolean
  /** 有没有热更新下来的覆盖层（~/.jmreader/web） */
  overlay: boolean
  dist: string
  update: { enabled: boolean; url: string; auto: boolean }
}

/**
 * 检查更新的结果。
 * `error` 非空 = 这次没查成（连不上 / 还没发布 / 通道关着），界面安静地别提；
 * `available` = 有新版可装；`too_new` = 那版前端要更高的安装包版本，只能下新安装包。
 */
interface UpdateInfo {
  enabled: boolean
  app_version: string
  current_web: string
  available: boolean
  version: string
  web: string
  notes: string
  size: number
  url: string
  app_min: string
  too_new: boolean
  /** 这一版上次装上去没能开起来（已经被自动退回），别急着重装 */
  known_bad: boolean
  error: string
}

interface UpdateResult {
  ok: boolean
  /** false = 本来就没有新版 */
  changed: boolean
  version: string
  web: string
  files: number
  bytes: number
}

interface RollbackResult { ok: boolean; web: string; kept_at: string }

/** 磁盘账本：缓存 / 离线下载 / 用户数据各占多少 + 所在盘还剩多少 */
interface DiskUsage {
  cache_mb: number
  cache_limit_mb: number
  download_mb: number
  data_mb: number
  free_mb: number | null
  total_mb: number | null
  download_dir: string
  chapters: number
  offline_chapters: number
}

interface LogTail {
  path: string
  lines: string[]
  /** 日志比"最后 2 MB"还长（上面这些只是一部分） */
  truncated: boolean
  error: string
}

/** 磁盘上的一话：offline = 整本下载的离线副本，否则是随手补下的缓存 */
interface CachedChapter {
  photo_id: string
  album_id: string
  album_title: string
  index: string
  title: string
  state: string
  images: number
  total: number
  bytes: number
  offline: boolean
  mtime: number
}

interface AlbumOffline {
  album_id: string
  chapters: number
  done: number
  /** done >= chapters 才算"整本都能离线看" */
  offline: boolean
  images: number
  bytes: number
  dir: string
}

interface DesktopState {
  platform: string
  notify: boolean
  tray: boolean
  tray_live: boolean
  autostart: boolean
  hotkeys: boolean
  hotkeys_live: boolean
  hotkey_toggle: string
}

interface ExportResult {
  ok: boolean
  /** 用户在对话框里点了取消 */
  cancelled: boolean
  kind: string
  path?: string
  count?: number
  bytes?: number
}

interface ImportResult {
  ok: boolean
  cancelled: boolean
  kind: string
  path?: string
  imported?: number
  skipped?: number
}

/** 设置页的一个字段：kind 决定控件（表单是后端 settings_spec.py 那张表生成的） */
interface SettingsField {
  key: string
  label: string
  kind: 'text' | 'int' | 'float' | 'bool' | 'enum' | 'int_pair' | 'dir' | 'url'
  min?: number
  max?: number
  step?: number
  options?: string[]
  hint?: string
  restart?: boolean
  required?: boolean
}

interface SettingsSection { key: string; label: string; fields: SettingsField[] }
interface SettingsSpec { sections: SettingsSection[] }

type FolderKind = 'logs' | 'downloads' | 'data' | 'cache' | 'web' | 'app'
type ExportKind = 'favorites' | 'history' | 'settings' | 'all'
type DialogMode = 'open' | 'save' | 'folder'

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
  /** 设置页表单的定义（后端那张表）：加配置项不用改前端 */
  get_settings_spec(): Promise<SettingsSpec>
  /** 版本信息：app / web / 更新通道设置 */
  get_version(): Promise<VersionInfo>
  /** 查有没有新版前端；查不成把原因写在 error 里，不抛异常 */
  check_update(): Promise<UpdateInfo>
  /** 下载并装上前端更新（装完刷新页面即生效，exe 不动） */
  apply_update(force?: boolean): Promise<UpdateResult>
  /** 退回上一版前端 */
  rollback_update(): Promise<RollbackResult>
  /** 前端起来后报到一次：没报到的话下次开窗会把这份前端撤掉（自动回滚） */
  notify_booted(): Promise<boolean>
  /** 用系统浏览器打开链接（只放行 http / https） */
  open_url(url: string): Promise<boolean>
  /** 在资源管理器里打开 logs / downloads / data / cache / web / app 目录 */
  open_folder(kind: FolderKind): Promise<{ opened: boolean; path: string; reason?: string }>
  /** 桌面集成的实际状态（托盘起没起、快捷键注册上没有） */
  get_desktop_state(): Promise<DesktopState>
  /** 缓存 / 离线下载 / 用户数据各占多少 + 磁盘剩余 */
  get_disk_usage(): Promise<DiskUsage>
  /** 日志尾部（发日志给开发者用） */
  get_log_tail(lines?: number): Promise<LogTail>
  /** 按话下载（复用整本下载那套话单与状态机） */
  download_chapter(album_id: string, photo_id: string, index?: string, chapter_title?: string, title?: string, cover_url?: string): Promise<DownloadTask | null>
  /** 这本有没有完整的离线副本 */
  is_album_offline(album_id: string): Promise<AlbumOffline>
  /** 磁盘上有哪几话、各占多少地方（只读磁盘与本地库，不发请求） */
  list_cached_chapters(album_id?: string, limit?: number): Promise<CachedChapter[]>
  /** 删「最近阅读」：给了 photo_id 删这一话，没给删这本的全部 */
  remove_history(album_id: string, photo_id?: string): Promise<{ removed: number }>
  clear_history(): Promise<{ removed: number }>
  /** 导出用户数据（path 空着会弹"另存为"） */
  export_data(kind?: ExportKind, path?: string): Promise<ExportResult>
  /** 导入用户数据（path 空着会弹"打开文件"） */
  import_data(kind?: string, path?: string): Promise<ImportResult>
  /** 弹系统文件对话框；取消返回 null */
  create_file_dialog(mode?: DialogMode, filename?: string, directory?: string, file_types?: string[]): Promise<string[] | null>
}

interface PyWebview {
  api: PyApi
}

interface Window {
  pywebview?: PyWebview
}