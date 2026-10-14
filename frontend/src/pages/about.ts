// pages/about.ts

/**
 * 关于页（#/about）：导航栏左下角那对入口里的一个。
 *
 * README 里塞了开发、配置表、技术栈，那是给改代码的人看的；这一页只留用户真正
 * 用得上的三件事：能干什么、怎么用、数据在哪。所以两边内容允许重复，但别把
 * README 整段搬过来 —— 这一页的定位就是"精简版"。
 *
 * 外部链接走 `open_url`（交给系统浏览器），**不要**直接写 <a href>：这个壳里点 <a> 会把
 * 当前页顶掉、回不来（README 那种 GitHub 地址也一样，用按钮调 open_url 打开）。
 */
export function aboutPage(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'about-page'
  el.innerHTML = `
    <header class="page-head">
      <h1 class="page-title">关于</h1>
      <p class="page-sub">无广告的桌面漫画阅读器 · 阅读记录只存本机</p>
    </header>

    <div class="about-card">
      <img class="about-avatar" src="/apple-touch-icon.png" alt="" />
      <div>
        <p class="about-title">孤竹漫画 Guzhu Comic</p>
        <p class="about-sub">PyWebView + Vite 写的本地阅读器，图源走 JMComic-Crawler-Python。不用登录、没有广告；阅读记录、收藏、章节图都只在这台机器上。</p>
      </div>
    </div>

    <section class="about-section">
      <h2 class="about-h">能干什么</h2>
      <ul class="about-list">
        <li><b>搜索</b>：首页顶部那条搜索入口，按 <kbd>/</kbd> 也能进；最近 12 条搜过的词记在本机，点一下重搜、能单条删或一键清空；结果缓存 1 小时</li>
        <li><b>热门榜单</b>：最火三部做成弧形轮播，下面一条分类标签（全部 / 同人 / 单本 / 短篇 / 韩漫 / 美漫）各铺一行、行头右边「更多」进分类页；日 / 周 / 月与排序会记住</li>
        <li><b>详情页</b>：作者、标签、简介、热度、发布日期、相关作品，加一份可折叠的章节表；右边一栏只读评论，剧透默认盖住；详情缓存 24 小时</li>
        <li><b>开始 / 继续阅读</b>：读到第几页一直记着，回来点「继续阅读 · 第 N 页」接着看，上次那一话在章节表里描蓝</li>
        <li><b>阅读器</b>：连续滚动 / 单页翻页两种模式；图片宽度、页间距、背景色、自动滚屏在阅读设置里改，改完立即生效；一话读完图末有「下一话」的大按钮</li>
        <li><b>我的下载</b>：整本离线到本机，卡片上能暂停 / 继续 / 删除；关窗、断网、图源抖一下都只是停一会儿，下次接着下，只补缺的章节和缺的图</li>
        <li><b>收藏</b>：详情页右上角一颗心，存在本机、不需要登录，清缓存也不会丢；收藏过的本子在所有列表里封面右上角有「已收藏」小标</li>
        <li><b>为你推荐</b>：首页和搜索页各铺一段，按收藏的 tag / 作者、搜过的词打分，卡片副标题写明"为什么推它"；每段右边「换一批」接着翻，画像空就退化成热门排序</li>
        <li><b>论坛</b>：全站评论流，只读、不需要登录；每条评论下面挂一个封面条，点进去就是那本</li>
        <li><b>图片缓存与预加载</b>：章节图下载解密后留在本地，二次打开秒开、也能离线看；列表先铺骨架，详情缓存后台慢慢补，不挡点击</li>
        <li><b>外观</b>：深浅两套主题（左下角切换），窗口整体半透明毛玻璃，缓存在设置页里一键整理或清空</li>
      </ul>
    </section>

    <section class="about-section">
      <h2 class="about-h">怎么用</h2>
      <p class="about-text">
        最常走的一条路：<b>热门</b>或<b>搜索</b>找到本子 → 点进去是<b>详情</b> → 点<b>开始阅读</b> →
        顺手点右上角那颗心<b>收藏</b>；想离线就在详情页点<b>下载</b>，之后到左侧「我的下载」看进度。
      </p>
      <div class="about-keys">
        <span><kbd>/</kbd>回首页时直接进搜索</span>
        <span><kbd>←</kbd><kbd>→</kbd>翻页</span>
        <span><kbd>空格</kbd>下一页</span>
        <span><kbd>Home</kbd><kbd>End</kbd>最前 / 最后</span>
        <span><kbd>M</kbd>唤出阅读工具条</span>
        <span><kbd>Esc</kbd>收面板 / 返回</span>
      </div>
      <p class="about-text">
        阅读时工具条默认藏着，鼠标晃一下才出来；点屏幕中间收放工具条，点左右两侧翻页（设置里能关），
        最上面那条细线是这一话的进度。阅读模式、图片宽度这些在工具条里的<b>设置</b>浮层改。
      </p>
    </section>

    <section class="about-section">
      <h2 class="about-h">数据都在本机</h2>
      <ul class="about-paths">
        <li><code>~/.jmreader/data</code><span>阅读记录、收藏、搜索记录 —— 别删（能导出成 JSON 备份）</span></li>
        <li><code>~/.jmreader/downloads</code><span>整本下载的离线副本 —— 别删，删了得重下</span></li>
        <li><code>~/.jmreader/cache</code><span>章节图与接口缓存 —— 删了只是重新下，不丢记录</span></li>
        <li><code>~/.jmreader/web</code><span>热更新下来的前端（有这个目录就说明装过更新）</span></li>
        <li><code>~/.jmreader/logs</code><span>运行日志（按天切、留 7 天）—— 出问题发这个</span></li>
      </ul>
      <p class="about-text">
        窗口、阅读器、下载、推荐这些常用项在<b>设置</b>页里改，保存后写回 <code>config.yaml</code>，
        标了「重启生效」的要重开窗口才用得上。收藏、阅读记录、设置都能在设置页导出成 JSON。
      </p>
    </section>

    <section class="about-section">
      <h2 class="about-h">版本</h2>
      <p class="about-text version-line">读取中…</p>
      <div class="page-actions">
        <button type="button" class="mini-btn check-update-btn">检查更新</button>
        <button type="button" class="mini-btn open-channel-btn">更新通道</button>
        <button type="button" class="mini-btn open-logs-btn">打开日志目录</button>
      </div>
      <p class="about-text update-status"></p>
    </section>
  `

  const versionEl = el.querySelector<HTMLElement>('.version-line')!
  const statusEl = el.querySelector<HTMLElement>('.update-status')!
  const api = () => window.pywebview?.api

  async function loadVersion(): Promise<void> {
    const current = api()
    if (!current?.get_version) {
      versionEl.textContent = '（读不到版本：pywebview api 未就绪）'
      return
    }
    try {
      const info = await current.get_version()
      versionEl.textContent = `安装包 ${info.app} · 前端 ${info.web || '出厂那份'}`
        + `（${info.frozen ? '打包版' : '源码态'}）· 更新通道${info.update.enabled ? '开着' : '关着'}`
    } catch (err) {
      versionEl.textContent = '版本读取失败：' + String(err).replace(/^Error:\s*/, '')
    }
  }

  el.querySelector('.check-update-btn')!.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.check_update) return
      statusEl.textContent = '正在检查…'
      try {
        const info = await current.check_update()
        if (info.error) statusEl.textContent = `没查成：${info.error}`
        else if (info.too_new) statusEl.textContent = `有新版前端 ${info.version}，但要先换新版安装包`
        else if (info.available) statusEl.textContent = `有新版前端 ${info.version}：去「设置」页点「立即更新」`
        else statusEl.textContent = '已经是最新的'
      } catch (err) {
        statusEl.textContent = '检查失败：' + String(err).replace(/^Error:\s*/, '')
      }
    })()
  })

  el.querySelector('.open-channel-btn')!.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.get_version) return
      try {
        const info = await current.get_version()
        // 交给系统浏览器打开：这个壳里点 <a href> 会把当前页顶掉
        await current.open_url(info.update.url)
      } catch (err) {
        statusEl.textContent = '打不开：' + String(err).replace(/^Error:\s*/, '')
      }
    })()
  })

  el.querySelector('.open-logs-btn')!.addEventListener('click', () => {
    void (async () => {
      const current = api()
      if (!current?.open_folder) return
      try {
        const res = await current.open_folder('logs')
        if (!res.opened) statusEl.textContent = res.reason ?? `打不开：${res.path}`
      } catch (err) {
        statusEl.textContent = '打不开：' + String(err).replace(/^Error:\s*/, '')
      }
    })()
  })

  void loadVersion()
  return el
}