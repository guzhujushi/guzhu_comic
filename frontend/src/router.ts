type RouteHandler = (params: Record<string, string>) => HTMLElement | void

interface Route {
  path: string
  handler: RouteHandler
}

const routes: Route[] = []

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
  window.addEventListener('DOMContentLoaded', resolve)

  // 如果页面打开时没有 hash，默认跳到 /popular
  if (!window.location.hash) {
    window.location.hash = '/popular'
  } else {
    resolve()
  }
}