// 界面主题：暗色 / 浅色。只记在本地（localStorage，前缀跟 store.ts 一致），
// 不进 config.yaml —— 它跟"设置"那套（写回文件、可备份）不是一回事，换台机器重来就行。
//
// 第一帧用的那份是 index.html 里的内联脚本，读的是同一个 key，所以两边的格式必须一致。
import { pickKey, saveState } from './store.js'
import { themedReveal } from './motion.js'

export type Theme = 'dark' | 'light'

const KEY = 'theme'
const ALLOWED = ['dark', 'light'] as const

/** 当前主题：以 <html data-theme> 为准（内联脚本已经定好了），没写就是暗色 */
export function currentTheme(): Theme {
  return pickKey(document.documentElement.dataset.theme, ALLOWED, 'dark')
}

/**
 * 换主题：从 origin 处圆揭示扩散。改 dataset 和落盘都放进 apply，转场快照才拍得到新配色。
 *
 * 返回的 Promise 在配色真的换上去之后 resolve —— 转场那会儿回调不是同步跑的，
 * 调用方别写在 setTheme 的下一行（比如更新按钮上的图标和文字）。
 */
export function setTheme(origin: HTMLElement | MouseEvent | null, next: Theme): Promise<void> {
  if (next === currentTheme()) return Promise.resolve()
  return themedReveal(origin, () => {
    document.documentElement.dataset.theme = next
    saveState(KEY, next)
  })
}
