// 全站快捷键面板 + 一键「防社死」。挂在 body 上，任何页面都有效。
//
//   「?」（Shift+/）或 F1 —— 唤出 / 收起这张面板。
//   「P」          —— 防社死：停阅读器的自动滚屏、收浮层、整窗盖一层素底 + 一枚字标；
//                    再按一次 P（或点那层）回来。盖住期间其它按键一律吞掉 ——
//                    免得在遮罩底下还在翻页 / 换章，那才是最容易被"再看一眼"抓包的。
//
// 两条边界，别当成漏做：
//   * **真正把窗口藏起来**是桌面那份全局快捷键 `Ctrl+Alt+G`（Windows 注册的，前端碰不到它），
//     设置 → 桌面集成 → 全局快捷键 打开；面板里把这条写出来了。
//   * 本项目没有音频，"静音"没有对象 —— 不假装有。
import { brandMark } from './components/brand.js'

interface Shortcut { keys: string[]; label: string }
interface Group { title: string; items: Shortcut[] }

// 只写**真的存在**的键：写进去又按不出来的，比不写更糟
const GROUPS: Group[] = [
  {
    title: '全站',
    items: [
      { keys: ['/'], label: '首页上直接进搜索' },
      { keys: ['?'], label: '唤出 / 收起这张面板' },
      { keys: ['P'], label: '防社死：盖住画面、停自动滚屏' },
      { keys: ['Esc'], label: '收浮层 / 返回上一页' },
    ],
  },
  {
    title: '阅读器',
    items: [
      { keys: ['←', '→'], label: '上一页 / 下一页' },
      { keys: ['空格'], label: '下一页' },
      { keys: ['Home', 'End'], label: '最前 / 最后' },
      { keys: ['↑', '↓'], label: '单页模式下翻页' },
      { keys: ['M'], label: '唤出 / 收起工具条' },
    ],
  },
  {
    title: '桌面（Windows）',
    items: [
      { keys: ['Ctrl', 'Alt', 'G'], label: '隐藏 / 唤回窗口（设置里打开「全局快捷键」才有）' },
    ],
  },
]

let panel: HTMLElement | null = null
let cover: HTMLElement | null = null
let coverInner: HTMLElement | null = null
let panicked = false

function isTyping(target: EventTarget | null): boolean {
  const node = target as HTMLElement | null
  if (!node || !node.tagName) return false
  return node.tagName === 'INPUT' || node.tagName === 'TEXTAREA' ||
    node.tagName === 'SELECT' || node.isContentEditable
}

function buildPanel(): HTMLElement {
  if (panel) return panel
  const el = document.createElement('div')
  el.className = 'hotkey-sheet'
  el.hidden = true
  el.setAttribute('role', 'dialog')
  el.setAttribute('aria-label', '快捷键')
  el.innerHTML = `
    <div class="hotkey-card">
      <div class="hotkey-head">
        <h2 class="hotkey-title">快捷键</h2>
        <button type="button" class="hotkey-close" aria-label="关闭">✕</button>
      </div>
      <div class="hotkey-body"></div>
    </div>
  `
  const body = el.querySelector<HTMLElement>('.hotkey-body')!
  for (const group of GROUPS) {
    const head = document.createElement('p')
    head.className = 'hotkey-group'
    head.textContent = group.title
    body.appendChild(head)
    for (const item of group.items) {
      const row = document.createElement('div')
      row.className = 'hotkey-row'
      const keys = document.createElement('span')
      keys.className = 'hotkey-keys'
      for (const key of item.keys) {
        const kbd = document.createElement('kbd')
        kbd.textContent = key
        keys.appendChild(kbd)
      }
      const label = document.createElement('span')
      label.className = 'hotkey-label'
      label.textContent = item.label
      row.append(keys, label)
      body.appendChild(row)
    }
  }
  el.querySelector('.hotkey-close')!.addEventListener('click', closePanel)
  // 点卡片外面收掉（卡片自己放过）
  el.addEventListener('click', (event) => { if (event.target === el) closePanel() })
  document.body.appendChild(el)
  panel = el
  return el
}

function buildCover(): HTMLElement {
  if (cover) return cover
  const el = document.createElement('div')
  el.className = 'panic-cover'
  el.hidden = true
  el.setAttribute('role', 'presentation')
  const inner = document.createElement('div')
  inner.className = 'panic-inner'
  coverInner = inner
  el.appendChild(inner)
  el.addEventListener('click', () => setPanic(false))
  document.body.appendChild(el)
  cover = el
  return el
}

/** 字标要现取（buildCover 那一刻闪屏可能还没揭幕、也可能早撤了） */
function fillCoverInner(): void {
  if (!coverInner || coverInner.childElementCount) return
  const mark = brandMark(240)
  if (mark) coverInner.appendChild(mark)
  const title = document.createElement('p')
  title.className = 'panic-title'
  title.textContent = '已暂停'
  const sub = document.createElement('p')
  sub.className = 'panic-sub'
  sub.textContent = '再按一次 P 继续'
  coverInner.append(title, sub)
}

function openPanel(): void {
  const el = buildPanel()
  setPanic(false)
  el.hidden = false
}

function closePanel(): void {
  if (panel) panel.hidden = true
}

function togglePanel(): void {
  if (!panel || panel.hidden) openPanel()
  else closePanel()
}

/**
 * 防社死的总开关。除盖一层底之外，还会派 `guzhu:panic` 事件 ——
 * 阅读器接住它去停自动滚屏、收浮层、把进度落一次库（不然暂停期间的位置就丢了）。
 */
function setPanic(on: boolean): void {
  const el = buildCover()
  if (on === panicked) return
  panicked = on
  if (on) closePanel()
  fillCoverInner()
  el.hidden = !on
  if (on) document.documentElement.dataset.panic = '1'
  else delete document.documentElement.dataset.panic
  window.dispatchEvent(new CustomEvent('guzhu:panic', { detail: { on } }))
}

function onKey(event: KeyboardEvent): void {
  if (event.defaultPrevented) return
  // 组合键一律放过：Ctrl+Alt+G（藏窗口）、Ctrl+R、Ctrl+Shift+I 都得能用
  if (event.ctrlKey || event.altKey || event.metaKey) return

  if (panicked) {
    if (event.key === 'p' || event.key === 'P' || event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      setPanic(false)
      return
    }
    // 其余键只拦"应用自己要处理的"，不 preventDefault —— F5 / F12 这类归浏览器
    event.stopPropagation()
    return
  }

  if (event.key === 'Escape' && panel && !panel.hidden) {
    event.preventDefault()
    event.stopPropagation()
    closePanel()
    return
  }
  if (isTyping(event.target)) return

  if (event.key === '?' || event.key === 'F1') {
    event.preventDefault()
    togglePanel()
  } else if (event.key === 'p' || event.key === 'P') {
    event.preventDefault()
    setPanic(true)
  }
}

/**
 * 防社死开 / 关（给**阅读器工具条那颗遮罩按钮**用 —— 手机没键盘，按不了 P）。
 * 桌面走快捷键，这条只是同一件事的第二个入口。
 */
export function togglePanic(): void {
  setPanic(!panicked)
}

/** 装一遍就够（SPA 一进进程一次）；挂在捕获阶段，先于页面自己的 keydown 判掉 */
export function installShortcuts(): void {
  buildPanel()
  buildCover()
  window.addEventListener('keydown', onKey, true)
}
