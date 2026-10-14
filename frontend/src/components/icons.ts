// 图标统一从这里出：morphicons 的 <morph-icon> 自定义元素 + lucide 的图标数据（数据不是组件）
import { defineMorphIcon } from 'morphicons/element'
import type { IconInput } from 'morphicons/element'
import {
  ArrowLeft, BadgeInfo, BookOpen, Check, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, CircleCheck,
  Clock, Database, Download, Eraser, Flame, HardDriveDownload, Heart, HeartPulse, Info, List, Loader,
  FolderOpen, MessageSquareText, MessagesSquare, Moon, Pause, Play, RefreshCw, Save, ScrollText,
  Search, SearchCheck, Settings, SlidersHorizontal, Sun, Trash2, TrendingUp, Upload, Watch, X,
} from 'lucide'

defineMorphIcon()

/** 用到的图标都在这儿，改图标只动这里 */
export const icons = {
  back: ArrowLeft,
  read: BookOpen,
  prev: ChevronLeft,
  next: ChevronRight,
  down: ChevronDown,
  up: ChevronUp,
  chapters: List,
  close: X,
  play: Play,
  pause: Pause,
  settings: Settings,
  settingsOn: SlidersHorizontal,
  about: Info,
  aboutOn: BadgeInfo,
  save: Save,
  saved: Check,
  reload: RefreshCw,
  trim: Eraser,
  cache: Database,
  search: Search,
  searchDone: SearchCheck,
  searchBusy: Loader,
  popular: Flame,
  popularOn: TrendingUp,
  history: Watch,
  historyOn: Clock,
  download: Download,
  downloadOn: HardDriveDownload,
  downloadDone: CircleCheck,
  downloadBusy: Loader,
  heart: Heart,
  heartOn: HeartPulse,
  trash: Trash2,
  forum: MessagesSquare,
  forumOn: MessageSquareText,
  themeDark: Moon,
  themeLight: Sun,
  // 设置页后加的那几块（版本 / 磁盘 / 日志 / 导入导出）
  folder: FolderOpen,
  log: ScrollText,
  upload: Upload,
  update: RefreshCw,
} as const

export type IconName = keyof typeof icons

type Spring = 'smooth' | 'snappy' | 'bouncy'

export interface IconOptions {
  size?: number
  stroke?: number
  label?: string   // 给了就是有意义的图标，不给当装饰（aria-hidden）
}

/** 造一个 <morph-icon>，默认 16px 描边 1.8，跟着按钮文字颜色走 */
export function createIcon(icon: IconInput, opts: IconOptions = {}): HTMLElement {
  const el = document.createElement('morph-icon')
  el.setAttribute('size', String(opts.size ?? 16))
  el.setAttribute('stroke-width', String(opts.stroke ?? 1.8))
  el.reducedMotion = 'user'   // 系统开了减弱动效就直接换图，别硬飞
  el.icon = icon
  if (opts.label) el.setAttribute('label', opts.label)
  else el.setAttribute('aria-hidden', 'true')
  return el
}

/** 变形到另一个图标，默认 snappy：快、带一点点过冲 */
export function morphIcon(el: HTMLElement, icon: IconInput, spring: Spring = 'snappy'): void {
  ;(el as HTMLElementTagNameMap['morph-icon']).morphTo(icon, spring)
}

/** 模板里写了 <morph-icon> 的按钮，挂上去之后再把图标数据喂给它 */
export function setIcon(root: ParentNode, selector: string, icon: IconInput): HTMLElement {
  const el = root.querySelector<HTMLElement>(selector)!
  ;(el as HTMLElementTagNameMap['morph-icon']).icon = icon
  el.setAttribute('aria-hidden', 'true')
  return el
}