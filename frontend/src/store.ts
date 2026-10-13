// 界面状态的本地记忆：只记用户的选择（榜单 / 分类 / 排序 / 搜索范围），
// 丢了就回默认值，所以不进 config.yaml（那是"设置"的正式出口：写回文件、可备份、带校验）
const PREFIX = 'guzhu:'

/** 读一段界面状态：没有 / 存坏了 / localStorage 被禁用，一律回退默认值 */
export function loadState<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(PREFIX + key)
    if (raw === null) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

/** 存一段界面状态；隐私模式 / 存储被禁用时静默放弃，别为记个偏好打断用户 */
export function saveState(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value))
  } catch {
    /* 记不住偏好不影响阅读 */
  }
}

/** 从候选值里挑一个：老数据 / 人手改过的值认不出来就回退默认 */
export function pickKey<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  if (typeof value === 'string' && (allowed as readonly string[]).includes(value)) return value as T
  return fallback
}
