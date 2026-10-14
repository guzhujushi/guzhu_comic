import { renderError } from './components/states.js'

type RouteHandler = (params: Record<string, string>) => HTMLElement | void

interface Route {
  path: string
  handler: RouteHandler
}

const routes: Route[] = []

/** 当前页面注册的收尾函数（存进度、解绑监听之类），路由切走前统一执行 */
const cleanups: (() => void)[] = []

export function onUnmount(fn: () => void): void {
  cleanups.push(fn)
}

function runCleanups(): void {
  for (const fn of cleanups.splice(0)) {
    try {
      fn()
    } catch (err) {
      console.error(err)
    }
  }
}

export function registerRoute(path: string, handler: RouteHandler) {
  routes.push({ path, handler })
}

export function navigate(path: string) {
  window.location.hash = path
}

function parseHash(): { path: string; params: Record<string, string> } {
  const raw = window.location.hash.slice(1) || '/'  // 去掉开头的 #
  const [path, queryString = ''] = raw.split('?')

  const params: Record<string, string> = {}
  if (queryString) {
    for (const [k, v] of new URLSearchParams(queryString)) {
      params[k] = v
    }
  }

  return { path, params }
}

function resolve() {
  runCleanups()
  const { path, params } = parseHash()

  const container = document.querySelector<HTMLDivElement>('#app')
  // 页面结构不对（index.html 被改过）时，至少别把异常抛进事件回调里
  if (!container) return

  for (const route of routes) {
    if (route.path !== path) continue
    container.innerHTML = ''
    try {
      const result = route.handler(params)
      if (result) container.appendChild(result)
    } catch (err) {
      // 页面**挂载那一刻**就抛异常的话，container 已经被清空了 —— 不兜这一下就是整窗空白、
      // 连一句提示都没有（各页面自己的 try/catch 管的是它们之后的异步加载，管不到这里）。
      console.error(`页面渲染失败：${path}`, err)
      container.innerHTML = ''
      renderError(container, `这个页面没能打开（${path}）：${String(err)}`, resolve)
    }
    return
  }

  // 没有匹配的路由
  container.textContent = `404: ${path}`
}

export function startRouter() {
  window.addEventListener('hashchange', resolve)

  // 没有 hash 就默认跳 /popular（赋值会触发 hashchange -> resolve）；
  // 不再监听 DOMContentLoaded：它和首次 hashchange 会让首页被渲染两遍
  if (window.location.hash) {
    resolve()
  } else {
    window.location.hash = '/popular'
  }
}