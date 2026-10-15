// tmp/ 临时假桥（只为在手机尺寸下看版式，不进产物）：
// 把 window.pywebview.api.X(...) 原样转成一个 POST /_api，PC 那边拿真后端回答。
// 方法引用必须**稳定**（webstatus.ts 的闸门靠"引用变没变"判断 pywebview 又注入了一遍）。
(function () {
  const cache = new Map()
  function call(name, args) {
    return fetch('/_api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, args }),
    }).then(async (res) => {
      const text = await res.text()
      let data
      try { data = JSON.parse(text) } catch (e) { throw new Error('假桥回了非 JSON：' + text.slice(0, 200)) }
      if (data && data.__error__) throw new Error(data.__error__)
      return data && data.__result__
    })
  }
  window.pywebview = {
    api: new Proxy({}, {
      get(_t, name) {
        if (typeof name !== 'string') return undefined
        // then/catch/finally 必须回 undefined：代理对任何属性都回函数，会让 api 本身变成
        // 一个 thenable —— 于是 await api 去调 then(resolve, reject)，promise 永不 settle，
        // 整个启动流程挂在 await 上（实测就是这个坑）
        if (name === 'then' || name === 'catch' || name === 'finally') return undefined
        if (!cache.has(name)) cache.set(name, (...args) => call(name, args))
        return cache.get(name)
      },
    }),
  }
  // 给截图用的：?scrollto=.selector 自动滚到那个元素，?click=.selector 再点一下。
  // 手势 swipe 落点不好控，页面又长（78 话），所以让假桥代劳。
  const q = new URLSearchParams(location.search)
  const preset = q.get('auto')
  if (preset === 'tabs') {
    const report = (tag) => {
      const el = document.querySelector('.board-tabs')
      if (!el) { fetch('/report', { method: 'POST', body: tag + ' 没有 .board-tabs' }); return }
      const cs = getComputedStyle(el)
      fetch('/report', { method: 'POST', body: tag + ' scrollWidth=' + el.scrollWidth + ' clientWidth=' + el.clientWidth +
        ' scrollLeft=' + el.scrollLeft + ' overflowX=' + cs.overflowX + ' 子项=' + el.children.length })
    }
    setTimeout(() => {
      report('[量测]')
      const el = document.querySelector('.board-tabs')
      if (el) { el.scrollLeft = 220; setTimeout(() => report('[设 scrollLeft=220 之后]'), 600) }
    }, 9000)
  }
  const scrollTo = preset === 'comment' ? '.comment-toggle' : q.get('scrollto')
  const clickSel = preset === 'comment' ? '.comment-toggle' : q.get('click')
  if (scrollTo || clickSel) {
    setTimeout(() => {
      const target = document.querySelector(scrollTo || clickSel)
      if (!target) { console.log('[假桥] 没找到 ' + (scrollTo || clickSel)); return }
      target.scrollIntoView({ block: 'center' })
      if (clickSel) setTimeout(() => document.querySelector(clickSel).click(), 500)
      console.log('[假桥] 已定位 ' + (scrollTo || clickSel))
    }, 9000)
  }
  console.log('[假桥] 已挂上')
})()