/** 应用设置：读的是后端 config.yaml，进程内缓存一份（保存后用 loadSettings(true) 重新拉） */
export interface AppSettings {
  window: {
    title: string
    width: number
    height: number
    min_size: number[]
    glass: 'none' | 'mica' | 'acrylic' | 'tabbed'
    glass_opacity: number
  }
  dev: { url: string; debug: boolean }
  reader: {
    restore_progress: boolean
    click_to_page: boolean
    mode: 'webtoon' | 'single'
    background: 'dark' | 'black' | 'gray' | 'light'
    page_gap: number
    auto_scroll: number
    width: number
  }
  detail: {
    chapters_collapse: number
    comment_preview: number
  }
  prefetch: {
    albums: number
    chapter_images: number
    next_at: number
  }
  download: { workers: number }
  cache: {
    photo_ttl: number
    album_ttl: number
    search_ttl: number
    ranking_ttl: number
    comment_ttl: number
    max_size_mb: number
    cleanup_interval: number
  }
}

/** 和后端 DEFAULT_CONFIG 保持一致：桥没就绪或读失败时兜底，别让页面直接炸 */
export const DEFAULT_SETTINGS: AppSettings = {
  window: {
    title: 'Guzhu Comic', width: 1200, height: 800, min_size: [800, 600],
    glass: 'none', glass_opacity: 0.92,   // 浏览器里没有 DWM，兜底不要玻璃
  },
  dev: { url: 'http://localhost:5173', debug: true },
  reader: {
    restore_progress: true, click_to_page: true,
    mode: 'webtoon', background: 'dark', page_gap: 0, auto_scroll: 0, width: 1080,
  },
  detail: { chapters_collapse: 20, comment_preview: 5 },
  prefetch: { albums: 12, chapter_images: 3, next_at: 0.9 },
  download: { workers: 8 },
  cache: {
    photo_ttl: 86400, album_ttl: 86400, search_ttl: 3600, ranking_ttl: 3600, comment_ttl: 600,
    max_size_mb: 2048, cleanup_interval: 600,
  },
}

let cached: AppSettings | null = null

/** 读配置；默认走缓存，force=true 时重新问后端要 */
export async function loadSettings(force = false): Promise<AppSettings> {
  if (cached && !force) return cached
  const api = window.pywebview?.api
  if (!api?.get_settings) return DEFAULT_SETTINGS
  try {
    const raw = (await api.get_settings()) as Partial<AppSettings>
    cached = {
      ...DEFAULT_SETTINGS,
      ...raw,
      window: { ...DEFAULT_SETTINGS.window, ...raw.window },
      dev: { ...DEFAULT_SETTINGS.dev, ...raw.dev },
      reader: { ...DEFAULT_SETTINGS.reader, ...raw.reader },
      detail: { ...DEFAULT_SETTINGS.detail, ...raw.detail },
      prefetch: { ...DEFAULT_SETTINGS.prefetch, ...raw.prefetch },
      download: { ...DEFAULT_SETTINGS.download, ...raw.download },
      cache: { ...DEFAULT_SETTINGS.cache, ...raw.cache },
    }
  } catch (err) {
    console.error('读配置失败，用默认值', err)
    cached = DEFAULT_SETTINGS
  }
  return cached
}
