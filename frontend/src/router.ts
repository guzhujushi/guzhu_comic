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

  for (const route of routes) {
    if (route.path === path) {
      const container = document.querySelector<HTMLDivElement>('#app')!
      container.innerHTML = ''
      const result = route.handler(params)
      if (result) container.appendChild(result)
      return
    }
  }

  // 没有匹配的路由
  const container = document.querySelector<HTMLDivElement>('#app')!
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