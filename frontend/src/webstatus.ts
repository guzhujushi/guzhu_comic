export function waitForPywebview(timeoutMs = 5000): Promise<PyApi> {
  // 已经就绪，直接返回
  if (window.pywebview?.api) {
    return Promise.resolve(window.pywebview.api)
  }

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      window.removeEventListener('pywebviewready', onReady)
      reject(new Error('pywebview 初始化超时'))
    }, timeoutMs)

    const onReady = () => {
      clearTimeout(timer)
      window.removeEventListener('pywebviewready', onReady)

      if (window.pywebview?.api) {
        resolve(window.pywebview.api)
      } else {
        reject(new Error('pywebviewready 触发了但 api 仍不存在'))
      }
    }

    window.addEventListener('pywebviewready', onReady)
  })
}

/**
 * 桥还没注入好时"盯着它"：真就绪了再回来接着干活。
 * 启动那一下偶尔会慢半拍，页面这边别一看到没有 api 就报死错误。
 */
export function waitForApi(tries = 24, gap = 500): Promise<PyApi> {
  const ready = window.pywebview?.api
  if (ready) return Promise.resolve(ready)
  return new Promise((resolve, reject) => {
    let left = tries
    const timer = window.setInterval(() => {
      const api = window.pywebview?.api
      if (api) {
        window.clearInterval(timer)
        resolve(api)
        return
      }
      if (--left <= 0) {
        window.clearInterval(timer)
        reject(new Error('pywebview api 一直没就绪'))
      }
    }, gap)
  })
}
