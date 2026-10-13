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