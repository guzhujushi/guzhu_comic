// 「文字 + 箭头」下拉：榜单、排序、搜索范围共用这一个控件和 .rank-* 那套样式
import { createIcon, icons, morphIcon } from './icons.js'

export interface PickerItem<T extends string> {
  key: T
  label: string
}

export interface Picker<T extends string> {
  el: HTMLDivElement
  /** 只改按钮文字和菜单高亮，不触发 onPick（页面自己管状态时用） */
  set(key: T): void
  close(): void
  isOpen(): boolean
}

export function createPicker<T extends string>(
  items: PickerItem<T>[],
  onPick: (key: T) => void,
): Picker<T> {
  const el = document.createElement('div')
  el.className = 'rank-picker'

  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'rank-btn'
  btn.setAttribute('aria-haspopup', 'true')
  btn.setAttribute('aria-expanded', 'false')

  const label = document.createElement('span')
  label.className = 'rank-label'

  const caret = createIcon(icons.down, { size: 14, stroke: 1.8 })
  caret.classList.add('rank-caret')

  btn.append(label, caret)

  const menu = document.createElement('div')
  menu.className = 'rank-menu'
  menu.hidden = true

  for (const item of items) {
    const option = document.createElement('button')
    option.type = 'button'
    option.dataset.key = item.key
    option.textContent = item.label
    option.addEventListener('click', () => {
      close()
      onPick(item.key)
    })
    menu.appendChild(option)
  }

  el.append(btn, menu)

  function close(): void {
    menu.hidden = true
    btn.setAttribute('aria-expanded', 'false')
    morphIcon(caret, icons.down)
  }

  btn.addEventListener('click', (event) => {
    event.stopPropagation()   // 别让 document 上那个"点空白收起"的监听顺手把它关掉
    const open = menu.hidden
    menu.hidden = !open
    btn.setAttribute('aria-expanded', String(open))
    morphIcon(caret, open ? icons.up : icons.down)
  })

  return {
    el,
    set(key) {
      label.textContent = items.find((item) => item.key === key)?.label ?? ''
      for (const option of Array.from(menu.querySelectorAll<HTMLButtonElement>('button'))) {
        option.classList.toggle('active', option.dataset.key === key)
      }
    },
    close,
    isOpen: () => !menu.hidden,
  }
}
