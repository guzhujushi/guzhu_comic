# STATUS — 当前进度

> 项目：孤竹漫画（guzhu_comic）。仓库根：`D:\guzhu_comic`。
> 交接背景见 `tmp/交接文档.md`；能力评估见 `tmp/后端能力接入评估.md`。
> 按用户要求，本项目不建 `docs/` 与根目录 `STATUS.md`，文档统一放 `tmp/`。

## 任务清单

- [x] 评估「哪些后端能力值得做进前端」（`tmp/后端能力接入评估.md`，2026-10-13）
- [x] A1 搜索页「搜索范围」下拉：站内 / 作品名 / 作者 / 标签 / 角色（2026-10-13）
- [x] A2 搜索 + 榜单「排序」切换：最新 / 观看 / 收藏 / 评分 / 图片数 / 评论数（2026-10-13）
- [x] B2 榜单 / 搜索条件持久化（localStorage，零后端）（2026-10-13）
- [x] A3 详情页补字段（发布日期 / 更新日期 / 评论数）+「相关作品」卡片（2026-10-13）
- [x] B1 详情页评论预览 —— 做成右侧评论区（只读、不需要登录）（2026-10-13）
- [x] 详情页章节折叠 + 折叠时「跳到上次读到的那话」（2026-10-13）
- [x] B4 本地收藏 + 「我的收藏」页（**不登录**：本地 sqlite 表 + 详情页心形 + `#/favorites`）（2026-10-13）
- [x] 热门榜单改版：按分类分区（每类一行 / 右侧「更多」进分类页 / 卡片虚化入场 / 分类标签条与面板接成一块）（2026-10-13）
- [x] 卡片悬浮手感：鼠标悬停再放大一点 + 加阴影（2026-10-13）
- [x] 首页 hero 去重：hero 展示的那三部，下面的推荐段与各分类横条里不再出现（2026-10-14）
- [x] 首进首页空白**真根因**修复：`API.client` / `API.download_dir` 是**公开**属性 → pywebview 注入桥时 `dir()`+`getattr()` 把它们递归展开（447 条，还现场把 jmcomic 客户端建出来 0.855s）→ 两步注入窗口被拉到秒级、WebView2 又注两遍 → 第二遍重建在飞回调表 → promise 永不 settle → `await loadSettings()` 挂死、**整窗空白**。改名 `_jm` / `_download_dir`（35 条 / 0.000s，桥就绪 ~100ms）；前端补 `waitForBridge` 静默窗 + `bridgeCall`（2026-10-14）
- [x] 首进首页缺失修复：「为你推荐 / 热门推荐」段与左下角「继续阅读」卡**冷启动自愈** —— 启动闸门改成等桥**挂好方法**（`waitForBridge`）+ 这两块各自失败重试；闸门的「安静窗」改为按**方法引用变化**判重注入（只听 `pywebviewready` 会漏），`quietMs` 400→800（2026-10-14）
- [x] 首屏 / 论坛「加载不出来」修复：客户端懒加载 + 后台预热、虚化入场兜底、失败自动重试、窗口回前台自愈（2026-10-14）
- [x] B5 「论坛」页（= 全站评论流 `forum_pagination`，只读、不登录）：左侧导航「论坛」+ `#/forum`，评论下面挂进本子的封面条（2026-10-13）
- [x] 搜索记录（最近搜索 12 条：搜索页 chips 点一下重搜 + 单条删除 / 清空）（2026-10-14）
- [x] 缓存策略 / 预加载：列表铺封面 + 标题后预热详情、进详情页预下要读那话的前几张、一话看到 90% 预加载下一话（2026-10-14）
- [x] 推荐算法一期：搜索记录落库 + 收藏 tag / 作者快照 + 首页第一段 / 搜索页结果下方的「为你推荐」（热度候选池 + 画像打分 + 换一批）+ 所有列表的「已收藏」角标（2026-10-14）
- [x] 首页推荐段「没了」核对：确认是画像空 → `cold=True` → 标题退化成「热门推荐」的正常 fallback（真桥探针 `tmp/_probe_app.py` 实测：段子在、10 张卡），不是 bug（2026-10-14，见 `tmp/交接文档.md` §5.15）
- [x] 不做：A4「只看汉化」（**2026-10-14 用户定：不做**；真要做需先引入 `impl='html'` 的第二客户端，见评估 §3）
- [x] B3 整本离线下载 + 「我的下载」页 + 详情页同排下载按钮（2026-10-14）
- [x] B6 开场动画（GuZhu 字标描边 + 闪屏预热 + 飞入左上角）（2026-10-14）
- [x] 开场字标落位定稿：品牌行 = 字标 + 「漫画」（用户 2026-10-14 定「只换 guzhu」），落点 `.brand-slot`、导航字标收到 76px（2026-10-14）
- [x] 搜索页「进详情再返回」修复：关键词进地址栏（`#/search?q=…`，`replaceState`），挂载按 `params.q` 还原且不重复记搜索记录（2026-10-14）
- [x] 详情页区块顺序：章节列表提到「相关作品」前面（2026-10-14）
- [x] 阅读器浮层不做毛玻璃（用户 2026-10-14 定「漫画的内容不要做毛玻璃特效」）：五个浮层删 `backdrop-filter` + 底色填实（2026-10-14）
- [x] UI 动效 / 质感一期：`--ease-spring` + 按钮 `:active` 回弹、卡片多层材质（近影 + 远影 + 1px 内高光）、"网点"加载签名（闪屏圆点进度条 / 骨架屏 / 章节等待统一）、
      空状态漫画气泡、阅读纸纹（feTurbulence 噪点层）、暗/浅双主题 + `clip-path: circle()` 圆形揭示、封面 → 阅读器共享元素转场（2026-10-14）
- [x] 不做：一切账号体系（登录 / 网页端收藏 / 签到 / 发评论）—— 会落地账号凭据，有隐私风险（2026-10-13 定）
- [x] 打包分发评估（`tmp/打包分发设计.md`）：onedir 方案 / 端口 47753 / 本地静态服务挂 `frontend/dist` / 误报清单 / 跨平台边界；配套 `scripts/build_exe.ps1` + `tmp/_probe_exe.py`（2026-10-14，冻结态实测通过：开窗、桥往返、30 张卡、localStorage 可写、38.9 MB）
- [x] 阅读器：点目录 / 设置浮层外面就收起它（那一下不再顺手翻页 / 收工具条），面板开着时滚轮让给面板（2026-10-14）
- [x] 左下角「继续阅读」：一张卡（最近读过的那本 + 封面 + 读到第几页）+ 一个按钮，点了直接进阅读器落回上次那页；没读过就整块藏起来（2026-10-14）
- [x] README 页首加「亮点」段（数据不出本地 / 能反复读 / 接着上次看 / 推荐真算 / 无广告 / 现代桌面壳…）（2026-10-14）
- [x] 导航栏「设置」移到底部左下角 + 新增「关于」页（`#/about`：能干什么 / 怎么用 / 数据在哪，README 的用户视角精简版）（2026-10-14）
- [x] 健壮性审计（用户："不加功能了，看看代码有没有漏洞，补齐漏洞和可能崩溃的地方，最后检验"）：全库只读审查 →
  补 13 处"会整窗空白 / 会静默丢数据 / 会以 TypeError 直穿 JS 桥 / 会信息暴露"的点 + 新增 3 个回归脚本（2026-10-14）
- [x] 打包 P0 落码（2026-10-14 完成，见下面「打包落地」一节）：`backend/paths.py` + `backend/server.py`（静态服务，页面与图同源）+ `main.py` 起服务 + `dev.use_dev_server` / `server.port` + `private_mode=False, storage_path=~/.jmreader/webview`；已出包并过验收（onedir 39 MB / zip 19.9 MB）
- [x] 打包 P1 之二（2026-10-14）：**单实例检测**（命名互斥体，第二个实例弹一句提示 + 把已有窗口拉到前台后退出）
  + **WebView2 缺失提示**（查 EdgeUpdate 注册表 `pv`，缺了就给人话提示并自动打开微软下载页，不再是对着一个白窗口）
- [x] 打包 P1 收尾（2026-10-14，用户："先把 p1 落地，把需要完善的完善好再打包扫描"）：**日志落盘**
  （`backend/logging_setup.py`：`~/.jmreader/logs/app.log` 按天切留 7 天 + Tee 掉 stdout/stderr + 未捕获异常/后台线程异常
  连栈落盘；顺手把 jmcomic 自带的 stdout handler 收编，不然每条 jm 日志在文件里重两遍）
  + **256×256 图标源图**（`frontend/public/apple-touch-icon-256.png`，构建脚本优先用它生成 `.ico`；
  原来的 180 源图根本产不出 256 那一帧 —— Pillow 写 ICO 只缩不放）
  + `frontend/index.html` 标题 `frontend` → `Guzhu Comic`
  + 跨平台兜底用例 `tmp/_check_platform_failopen.py`（非 Windows 上 glass / 单实例 / WebView2 三条都得放行）
  + 攒完改动**只打一次包**并过 Defender / VirusTotal：exe 2/75 报、zip 0/75 报，国内杀软全放行（见下面「第二次出包」）
- [x] 加固 + **第四次出包（2026-10-14，发布版，给同学用之前）**：图片文件名收口（`_img_name`）+ 本地服务 **Host 白名单**
  + 运行足迹 / 中文路径 / 打包态 Host 三类验收（见下面「第三次出包」「第四次出包」）
- [x] 体验三项（2026-10-14，用户从“还能优化什么”里挑的**前三项**）：
  ①「返回就到原处」—— 全站滚动位置 + 分类页 / 论坛页码写进地址；②详情页作者 / 标签可点，一下按它重搜；
  ③阅读器工具条按指针位置分上下唤出（第四项“下载页总占用 / 按话下载 / 导出”按用户要求**先砍掉**）

## 体验三项（返回还原 / 作者标签可点 / 工具条分上下唤）改动清单（2026-10-14）

用户从「还有什么可以优化体验的地方」那份清单里挑了**前三项**做；第四项（下载页总占用 / 剩余空间、按话下载、导出成文件包）
**按用户要求先砍掉**（见「下一步」第 4 条）。

### ① 返回就到原处：全站滚动位置 + 分类页 / 论坛页码

- `frontend/src/router.ts`（这轮的重头；`tmp/交接文档.md` §5.23 有完整的"为什么这么写"与三个坑）：
  - `scrollMemo`（`地址（参数排序后）→ 离开时看到哪儿了`，上限 60 条）+ `currentKey`（屏幕上这一页的地址）+ `rememberScroll()`；
    **在 `resolve()` 开头、也就是"离开这一页"的瞬间记一次**，键用 `currentKey` —— 这会儿地址栏已经是新地址了，
    现读 `location.hash` 会记到新页面名下。这块记忆**只活在这一次会话**，不落盘。
  - `traversed` 不再靠 `popstate` 判：**Chrome 在 hash 变化时也会甩一个 popstate**（跟 hashchange 前后脚到），
    于是"点导航进新页面"也被当成退回来（实测位置卡在 500 不回顶）。改成给每条历史记录盖**递增序号**（`history.state.__seq`）：
    序号跟当前这条不一样 = 历史穿梭（前进 / 后退）；一样或没盖过章 = 页面自己写 hash 推出来的新条目。
  - 新增并导出 `replaceHash(next)`：只改地址栏、不往历史里堆一条，**且把序号章原样带过去**（裸 `replaceState` 会把章冲掉 ——
    那样"从详情退回这一条"就认不出来：页码能对上，滚动位置会丢）。搜索页 / 分类页 / 论坛页的 `syncUrl()` / `syncPage()` 都改走它。
  - 新增并导出 `pageParam(params, max = 60)`：读地址里的页码，认不出 / 越界都当第 1 页。
  - `restoreScroll(target)`：定时器重试（页面是"先骨架、后数据"长出来的，一次 `scrollTo` 打不到底），用户一滚轮 / 一触摸就放手；
    另把 `history.scrollRestoration` 置 `'manual'` —— 浏览器自己也有一套滚动还原，会在 hash 切完之后再把我们那下顶掉。
  - 阅读器（`/read`）两边都不管：它有自己的"回到第 N 页"（进度恢复）。
- `frontend/src/pages/category.ts` + `board.ts`：签名改 `boardPage(分类, startPage = 1)`；页码写进地址（`syncPage()` → `replaceHash`）；
  挂载时按地址里的页码把前面几页**顺序补齐**（`while (!home && !dead && !done && page < startPage)`，没进展就退出、防空转）。
- `frontend/src/pages/forum.ts`：`forumPage(params)` 读 `pageParam`；`syncPage()` 写 `#/forum?page=N`；启动器同样顺序补齐。
- **顺手修掉的两个真 bug**：
  1. **分类页第一次点「加载更多」会把第 1 页再要一遍**（卡片重复 + 页码整体错一位）—— `load()` 里只 `page = 0`，从没置过 1。
     现在拿到第一页就 `page = 1`（top 只 `slice(3)` 进列表，不会重复）。
  2. **搜索页 `syncUrl()` 只写 `q`，把 `scope` / `sort` 丢了** —— 从详情点标签 / 作者进来再返回，会按 localStorage 里
     "上次用的条件"重搜，结果跟当时那批对不上。现在非默认值才追加 `&scope=` / `&sort=`（地址形如 `#/search?q=X&scope=author`）。
- 回归：新增 `tmp/_check_back_restore.py`（无头 Chrome + 假桥 + dist 副本）—— **19 条全绿**：A 搜索→详情→返回、
  B 分类页翻两页→详情→返回、C 论坛翻页→详情→返回，外加一条对照面「点导航进新页面该回顶部（不是接着上一页的位置）」。

### ② 详情页作者 / 标签可点

- `pages/detail.ts`：作者换成 `<a class="meta-link" href="#/search?scope=author&q=…">`，标签 `<span class="tag">` 换成
  `<a class="tag" href="#/search?scope=tag&q=…">`（一个 `searchHref(scope, value)` 拼地址，就在 `renderDetail()` 前面）。
- `style.css`：给 `.meta-link` 与 `.tags .tag` 补 hover（`.tags` 前缀是为了压过 `.detail-hero .tag` 的权重）。
- 点下去走的是搜索页本来就有的 `?q=&scope=` 还原路径（§5.20 那条），不新增接口。
- 回归：新增 `tmp/_check_detail_links.py`（9 条：链接在、`scope` 对、点下去真按那个范围发了 `search(...)`）**ALL PASS**。

### ③ 阅读器工具条按指针位置分上下唤出

- `pages/reader.ts`：原来是"鼠标一动两条一起亮"，现在按指针在屏幕上的位置分 —— 靠近上边（`TOP_ZONE = 110`）只亮
  `.reader-top`、靠近下边（`BOTTOM_ZONE = 150`）只亮 `.reader-dock`，**从中间过来两条都不动**（保持现状，不闪）；
  `showToolbar('top' | 'bottom' | 'both')` + `armHide()`（只重排倒计时，不叠加定时器）；hover 到哪条也亮哪条；
  目录 / 设置浮层开着时不动（那两条工具条是浮层的"把手"）。
- 回归：新增 `tmp/_check_reader_bars.py`（9 条）**ALL PASS**。

### 验证

- `npx tsc --noEmit` exit 0、`npm run build` exit 0。
- 无头回归全绿：`_check_back_restore.py`、`_check_detail_links.py`、`_check_detail_order.py`、`_check_reader_bars.py`、
  `_check_reader_glass.py`、`_check_search_back.py`、`_check_nav.py`、`_check_router_guard.py`、`_check_coldstart.py`、
  `_check_bridge_wipe.py`、`_check_hardening.py`。
- 真窗口冒烟 `tmp/_probe_bridge.py --dist`：`injects` 只有 **1** 次、`returnValueFAIL` 空、`missingApi` 空、首页照铺（推荐段 + 继续阅读卡都在）。

## 阅读器浮层去毛玻璃 改动清单（2026-10-14）

用户要求：**漫画的内容不要做毛玻璃特效**。

**口径（定下来）**：毛玻璃是"壳"的质感，**不许压在漫画图上**。全项目 `backdrop-filter` 现在只剩三处 ——
搜索入口那枚胶囊与搜索页整块壳（`.glass`）、封面角上那个收藏小徽章（`blur(2px)`）。阅读器的浮层原来是
`blur(18~24px)`，糊的正是底下的漫画图，这轮全撤。

**改法（只碰 `frontend/src/style.css`）**：`.reader-top` / `.reader-dock` / `.reader-sheet`（目录 + 设置共用）/
`.reader[data-mode="single"] .reader-end` / `.reader-toast` 五处删掉 `backdrop-filter` 与 `-webkit-backdrop-filter`，
同时把底色填实（`.55/.62/.68/.7/.9 → .88/.9/.92/.92/.94`）—— 模糊一撤，半透明黑直接压在白纸页上会把字糊住，
填实才看得清。位置 / 层级 / 动效 / DOM 一个都没动。

**验证**：新增 `tmp/_check_reader_glass.py`（无头 Chrome + 假桥 + dist 副本，单页模式给 2 张图），
量的是 `getComputedStyle().backdropFilter` 与底色 alpha —— **10/10 ALL PASS**：六个浮层全是 `none`、
顶栏与工具条底色 alpha ≥ .8、漫画图自己的 `filter` 也是 `none`（内容本身干净）。
另拍了对照图：`tmp/_ui/v11-reader-*.png`（改前，有模糊）vs `tmp/_ui/v13-reader-*.png`（改后），拍照脚本 `tmp/_shot_glass.py`。
回归：`tmp/_check_reader_sheet.py` 仍 ALL PASS、`tmp/_check_detail_order.py` 仍全绿；`tsc --noEmit` exit 0、`npm run build` exit 0。

**没动（说一声就顺手办）**：详情页 hero 那层"封面虚化"是 `.detail-hero::before` 的 `filter: blur(46px)` ——
它不是毛玻璃（不是 `backdrop-filter`，是封面自己糊出来的光晕底），所以这轮没碰；要是"漫画内容被糊"指的是它，删一条规则即可。
封面角上的收藏小徽章仍留着 `backdrop-filter: blur(2px)`（2px 几乎看不出，去掉会掉一点对比度）。

## 详情页区块顺序（章节提到「相关作品」前面）改动清单（2026-10-14）

用户要求：详情页的章节列表铺到「相关作品」**前面**去。

**改法（只碰 `frontend/src/pages/detail.ts`）**：`container.innerHTML` 模板里把「章节标题 + `.chapter-list` +
`.chapter-actions`」那一整段上移到 `${data.related.length ? ...}` 那一行**前面**。左栏顺序于是变成：
hero（封面 / 标题 / 作者 / 热度 / 日期 / 标签）→ 阅读·下载按钮 → 简介 → **章节（N）** → 相关作品。
后端的 `related` 字段、`paintChapters()`、折叠阈值一个都没动，只换了 DOM 顺序；`.related-list` 也没有专属样式（吃 `.album-list`）。

**验证**：新增 `tmp/_check_detail_order.py`（无头 Chrome + 假桥 + dist 副本，跟搜索页那个探针同一套脚手架；
假数据给 3 话 + 2 部相关作品）。8 条断言 **ALL PASS**：两个区块标题都在、章节标题排在相关作品标题前面、
`.chapter-list` 排在 `.related-list` 前面、简介仍在章节前面、「展开 / 收起」按钮紧跟着章节列表（没被相关作品隔开）、
章节 3 话与相关作品 2 张都按数据铺全。
先把源码改完、**没重建 dist** 跑了一遍就挂了 3 条 —— 这正好是最有用的反向对照（探针确实盯得住顺序）；
`npm run build` 之后全绿。`tsc --noEmit` exit 0、`npm run build` exit 0。

## 搜索页「进详情再返回」修复 改动清单（2026-10-14）

用户报：在搜索页点进详情、再点「返回」，落在一个**空搜索页**（看着像回首页），问是不是 hash 路由的问题。

**不是 router 的 bug，是页面状态的放法**：算用法问题。`pages/search.ts` 的关键词 / 结果全在页面局部变量里，
地址栏一直停在 `#/search`；点卡片只是往历史里 push 一条 `#/album?id=…`，所以 `history.back()` 回到的确实是
`#/search` —— 但那是**没带关键词的那条**，页面重建后自然是空的（下面还照铺推荐段，所以看着像首页）。
复现证据（先跑出来的，没修之前）：`hashAfterBack=#/search | kwAfterBack=空 | cardsAfterBack=0`。

**改法（只碰 `frontend/src/pages/search.ts`）**
- 搜索时把关键词写进地址：`#/search?q=…`（新增 `syncUrl()`，走 `history.replaceState`）。
  选 replace 不选 push 两头都要：① 换关键词不该在历史里堆一串记录（想退出去得按好几下）；
  ② 从详情返回时回到的正好是这条带关键词的记录。赋 hash 还会顺带触发 hashchange 白重渲染一遍。
- 挂载那条路老代码本来就有（"URL 带了 q 自动搜一次"），只是没人往地址里写；现在走 `doSearch(true)`：
  **不记搜索记录** —— `search_log` 的次数 / 时间是推荐画像的输入，跟着返回键刷上去就失真了。
- 关键词被清空后再点搜索：把地址里的 `q` 一并去掉，免得刷新 / 返回又冒出一个搜过的东西。
- 范围 / 排序不进地址（还是 localStorage 那份，`loadPrefs` 本来就"参数优先、其次上次用的"）。

**验证**
- 新增 `tmp/_check_search_back.py`（无头 Chrome + 假桥 + dist 副本；探针走外部 `probe.js`，
  用 `fetch('/report?d=…')` 回报给本地服务，Python 侧收 —— dump-dom / `document.title` 那条路偶尔读不到，白耗时间）。
  按用户报的路径走一遍：首页 → 搜索 → 搜「测试」→ 点第一张卡进详情 → 点详情「返回」→ 再换个词搜一次 → 再返回两次。
  **修复前 12 条里挂 7 条，修复后 12/12 ALL PASS**：搜完地址带词、结果 6 张、详情有返回按钮、
  返回回到那次搜索（输入框还是「测试」、结果 6 张）、返回不算新搜索（`log_search` 只被调 1 次）、
  换词再搜只改当前这条、再返回一次就离开搜索页（回到 `#/popular`，历史里没堆记录）。
- `tsc --noEmit` exit 0；`npm run build` exit 0。

**没做（可选）**
- 返回后**不还原滚动位置**（结果回来了，但列表从顶部开始）。要的话在 `search.ts` 用模块级变量记住
  `window.scrollY`、渲染完再 `scrollTo` 回去。
- 同类问题还留在别处：论坛「加载更多」的页码也在局部变量里（从详情返回会退回第 1 页）。
  要修就照这法子把页码写进地址：`#/forum?page=2`。

## 开场字标落位（只换「孤竹」）+ 待办核对 改动清单（2026-10-14）

用户口径三件事：① 开场落位**只换 guzhu**（品牌行留着「漫画」）；② A4「只看汉化」**不做**；
③ 待办里"有些是做过的" —— 按代码逐条核一遍再改文档。

**代码（这一轮只碰这一处，3 个文件）**
- `frontend/src/main.ts`：品牌行从 `<span class="brand-mark">孤竹漫画</span>` 拆成
  `<span class="brand-mark"><span class="brand-slot">孤竹</span>漫画</span>`。`.brand-slot` 是字标落点，
  里面那句「孤竹」是**兜底文案**（老 `index.html` 里没有闪屏那份 SVG 时照旧显示原文案，设计稿 §6 第 7 条的兜底因此还成立）。
- `frontend/src/splash.ts::placeNavMark()`：查询目标 `.brand-mark` → `.brand-slot`，只清这一格，「漫画」不碰。
- `frontend/src/style.css`：`.brand-mark` 改成 flex 行（`align-items: center` + `gap: 7px` + **`white-space: nowrap`**），
  新增 `.brand-slot`；`.brand-logo` 宽 **88px → 76px**。
- **为什么收窄**：`#nav` 只有 208px，扣掉留白 / 头像之后文字区 ≈ 124px；88px 字标 + 两个字（31px）超一格，
  「漫画」会被挤成**竖排**（88px 那版实测就是这样；`tmp/_ui/v10-brand-landed-zoom.png` 现在这张是 76px 之后的）。
  76px 时字标大写高 ≈ 15px，跟旁边 15px 的「漫画」齐平；飞行落位量的是实时矩形，改宽度不影响衔接。

**待办核对（按代码，不是按印象）**
- `related_list` **已经在用**：`backend/api.py::get_album_detail()` 返回的 `related` 就是 `album.related_list`，
  `frontend/src/pages/detail.ts` 拿它铺详情页「相关作品」那排卡（A3 那轮上的）—— 推荐设计稿 §11 早写了这条。
  推荐二期要做的只是**再拿它当图上的邻居**，不是"接入 related_list"。
- `get_taste_profile`：后端有（`api.py`）、类型有（`pywebview.d.ts`），**界面一处没接**（`frontend/src` 里搜不到调用点）。
- 阅读器双页 / 跨页模式、快捷键自定义、单页模式预加载相邻页：`pages/reader.ts` 里搜不到（未做）。
- 下载页总占用 / 剩余空间、按话下载、导出成文件包：`pages/downloads.ts` 与 `api.py` 都没有
  （`_dir_size()` 只喂缓存统计；`start_download()` 收的是话单，但 UI 只给"整本"一个入口）。
- 代码签名：`scripts/` 里没有任何 signtool / Authenticode 步骤（未做）。
- 顺手改掉两处过期表述：`tmp/交接文档.md` §0.5 的 `git log -1` 还写着 `c18417f`（实际 HEAD 已是
  `504454e 小更新`）；§0.5 补上"发布版之后又动过前端，`build_out/` 里的 dist 是旧的"。

**验证**
- `tsc --noEmit` exit 0；`npm run build` exit 0（CSS 39.15 kB / JS 112.50 kB）。
- 新增 `tmp/_shot_brand.py`（无头 Chrome + 假桥；**4 张图 + 4 条断言，ALL PASS / exit 0**）：
  图落在 `tmp/_ui/v10-brand-*.png`（落位后一行不折行 / 飞行中 / 1040px 窄屏整块藏（`.brand-text{display:none}`）/ 浅色）；
  `--dump-dom` 断言 —— 字标真的落在 `.brand-slot` 里、品牌行那一段只剩「漫画」、兜底文案「孤竹」已被换掉、
  落位后全文档只剩一份 `aria-label="GuZhu"`。
- 真窗口探针 `tmp/_probe_bridge.py --dist`：`returnValueFAIL=[]` / `missingApi=[]` / `appKids=1` / `rec=shown`（10 张）/
  `resume=shown` / `heroVsBelow={hero:3,dup:[]}` —— 启动路径没被这处改动带坏。
- 还没做：真机看一眼落位（飞行 + 对齐）；**发布版之后要重出包**（见「下一步」第 10 条）。

## 打包落地（P0 迁移）+ 杀软检测（2026-10-14）

用户要求：**先别加功能了，开始打包，再测测有哪个杀毒软件会报错**。

**落地的 P0 迁移**（设计见 `tmp/打包分发设计.md` §4）：
- 新增 `backend/paths.py`：`APP_DIR` / `DATA_DB` / `CACHE_DIR` / `IMG_DIR` / `WEBVIEW_DIR` + `is_frozen()` /
  `bundle_dir()` / `config_path()` / `dist_dir()` / `resolve_download_dir()` —— 源码态与冻结态的**唯一**分叉点，
  也是将来上 mac / Android 只改一处的地方（业务代码里没有 `sys.platform` / `sys.frozen`）。
- 新增 `backend/server.py`：`_QuietHandler` 从 `api.py` 搬过来（`api.py` 仍 re-export，老脚本 import 不破），
  加 `start_static_server(dist, extra_roots, port)` —— 一个端口同时喂 dist 与图片（页面与图**同源**），
  端口 47753 → 47760 依次退让、最后退回系统随机（换端口会打一行日志：origin 变了等于换一份 localStorage）。
- `backend/api.py`：`API(base_url=None)` —— 打包态复用 main 起的那个端口，源码态照旧自己起（端口 0 随机）。
- `backend/config.py`：`CONFIG_PATH = paths.config_path()`（冻结态 `~/.jmreader/config.yaml`）；`DEFAULT_CONFIG`
  补 `dev.use_dev_server: false` / `server.port: 47753`，并把 `dev.debug` 默认关掉（仓库那份 `config.yaml` 显式
  `use_dev_server: true` / `debug: true`，开发手感不变）；`save_config` 写前先建父目录。
- `main.py`：按 `dev.use_dev_server`（且非冻结）选 vite，否则起本地静态服务；`private_mode=False` +
  `storage_path=~/.jmreader/webview` 让 localStorage 活过重启；开窗前的任何异常弹 MessageBox（`--windowed`
  没有控制台，只 print 等于没提示）。
- `frontend/src/settings.ts` + `pages/settings.ts`：设置页补「用 vite 开发服务器」「本地服务端口」两项。
- `scripts/build_exe.ps1`：默认 `--windowed`（原来只有 `-Console` 分支，等于一直在打 console 子系统）。
- `backend/server.py` 顺手堵一个升级坑：`index.html` 加 `Cache-Control: no-store`（带 hash 的 js/css 照旧缓存）。

**踩到的坑**：探针副本与正式包**同源**（`http://127.0.0.1:47753`）+ **同一个 WebView2 用户目录** → 正式包首启时
页面从 HTTP 缓存拿到了上一轮探针注入的 `index.html`，把探针字串写进了刚写的 `config.yaml`。这不是产品 bug
（用户机器上这个 origin 只会有一条来源），但暴露了「`index.html` 被缓存 = 升级后老页面配新包 = 白屏」的真隐患，
已加 `no-store` 堵掉。验收脚本因此改成"跑前清 config.yaml + webview 目录"的真首启。

**产物**（`scripts/build_exe.ps1`，onedir 39 MB / zip 19.9 MB，约 26 秒；下表哈希是**补完两道闸之后**那次构建的）：
- `build_out/GuzhuComic/GuzhuComic.exe`（SHA256 `724A5BFF6FAC27E98DD41B9612B52B1D42F0127100833DF54C601CC2FDB2EC45`）
- `build_out/GuzhuComic-0.1.0-win64.zip`（SHA256 `9E7828C0C4796FBAEC39EA402A506F85EED80351EF333A52452CADBB2C6272A9`）

**验收**：
- `tmp/_check_exe_package.py`（真 exe 的**副本**，往 `index.html` 注入探针，走产品自己的桥回报）→ 全绿：窗口标题
  `Guzhu Comic`、`:47753/index.html` 就是包内 dist、`/images` 同源取图 200（164 KB）、`~/.jmreader/webview`
  403 个文件、页面回报 `kids=1|rec=shown|cards=10|resume=shown|rows=30`。
- `tmp/_check_exe_real.py`（**未改动**的正式包，真首启）→ 全绿：进程活着、窗口标题 `Guzhu Comic`、`:47753` 正常、
  首启写出 `~/.jmreader/config.yaml`（`title: Guzhu Comic` / `use_dev_server: false` / `debug: false` / `port: 47753`）。
- 老回归重跑：`_check_imgserver` / `_check_hardening` / `_check_api_smoke` 全绿；`tsc` / `npm run build` exit 0。
- **开窗前两道闸**（2026-10-14 补）：
  - `tmp/_check_webview2.py`（6/6）：本机 pv=`155.0.4283.45` → 已装；三个位置都查不到 / 空串 / `0.0.0.0` → 判定没装；
    注册表读不了（权限）→ **fail-open 放行**（宁可让 pywebview 自己报错，也不拦能跑的机器）。
  - `tmp/_check_single_instance.py`（5/5）：第一个进程拿到锁、第二个拿不到且自己退出、前一个退了又能拿到；
    `focus_existing()` 找不到窗口时返回 False 不抛异常。
  - `tmp/_check_webview2_gate.py`（6/6）：把 `installed()` 强制改成 False 跑一遍 `main()` —— 提示框出来、文案里有 WebView2 与
    「装好再双击」、自动打开 `https://go.microsoft.com/fwlink/p/?LinkId=2124703`、**不开白窗口**、点确定后线程正常结束。
  - `tmp/_check_exe_single.py`（真 exe）：第一个实例起窗口 → 开第二个 → 第二个弹「孤竹漫画已经在运行了」（class `#32770`）
    并 exit 0 → 第一个窗口原样还在。
  - 打包态能不能用上这两条，专门查过：`winreg` 是**内建模块**（`sys.builtin_module_names` 里有，不需要 `--hidden-import`），
    `webbrowser` 已在 PYZ 里 —— 否则这两条在 exe 里会静默失效（fail-open 把问题藏起来）。
  - 新产物 Defender 复扫：onedir / exe / zip 三处仍 **no threats**。

**杀软检测（只做了本机能做的）**：
- 本机**只装了 Windows Defender**（`root/SecurityCenter2` 只有它一项；引擎 4.18.26090.9 / 特征库 1.461.18.0）。
- `MpCmdRun -Scan -ScanType 3` 分别扫 **onedir 目录 / exe / zip** → 三处 **found no threats**；`Get-MpThreatDetection` 无历史告警。
- exe **未签名**（`Get-AuthenticodeSignature` → NotSigned）→ SmartScreen 会出「未知发布者」，这是误报画像里最重的一条，
  根治只能买代码签名证书（设计文档 §8-1）。
- ~~第三方引擎（360 / 火绒 / 腾讯）本机没有，VirusTotal 没测~~ —— **2026-10-14 用 VirusTotal 补上了**，
  见下面「第二次出包」一节（脚本 `tmp/_vt_scan.py` + `tmp/_vt_detail.py`，报告留在 `tmp/_vt/`）。

### 第二次出包：P1 收尾 + Defender / VirusTotal 双扫（2026-10-14）

用户口径：**"不要一次改动就打包一次，等改完再打包"** —— 这一轮就是攒完所有改动，只打了一次。

**这一轮改了什么**：
- `backend/logging_setup.py`（新）：日志落到 `~/.jmreader/logs/app.log`（按天切、留 7 天）；`sys.stdout` / `sys.stderr`
  接一层 Tee 进同一个文件（项目里大量 `print(..., flush=True)` 是给人的现场信息，没控制台不能丢）；
  `sys.excepthook` / `threading.excepthook` 连栈落盘（后台线程炸的最难查）；装不上只提示一句、**绝不拦开窗**。
  两处只在冻结态才有的坑：`--windowed` 下 stdout 可能是 `None`，异常钩子因此走 `logging` 而不是 `print`。
- `logging_setup._adopt_jmcomic_logger()`：jmcomic import 时给自己挂 `StreamHandler(sys.stdout)`，而我们装了 Tee →
  每条 jm 日志在文件里**写两遍**，还因为它的格式串要 `%(topic)s` 而给没带 topic 的记录抛一坨
  `Formatting field not found`。现在摘掉它那个 handler、只留 propagate，放个 `NullHandler` 占位（它 `if not handlers`
  才补），topic 用 filter 折进消息（`【api】…`）—— 文件里每条 jm 日志**只出现一遍**。
- `frontend/public/apple-touch-icon-256.png`（新，96 KB）：`apple-touch-icon.png` 只有 180×180，而 **Pillow 写 ICO
  只会缩不会放**（`IcoImagePlugin._save` 里 `size > 宽高` 直接 continue）→ 老包的最大一帧就是 180，任务栏大图标是放大糊的。
  256 那张是用 Pillow LANCZOS + 轻量 UnsharpMask 从 180 原图等比放大的（原画是平涂梗图，放大没有细节损失），
  `scripts/build_exe.ps1` 现在优先用 256 源图（没有就退回 180，尺寸表按源图尺寸裁）。
- `frontend/index.html`：`<title>frontend</title>` → `Guzhu Comic`（窗口标题由 pywebview 定，这个管浏览器/任务栏悬停）。
- `tmp/_check_logging.py`（新，**17/17**）：print / root logging / jmcomic logger / topic 折叠 / 主线程与后台线程异常 /
  重复 setup 不叠 handler / stdout 为 None / 日志目录建不出来时返回 None 不抛异常。
- `tmp/_check_platform_failopen.py`（新，**8/8**）：把 `sys.platform` 临时改成 darwin —— 毛玻璃整条跳过、单实例放行且
  真没建互斥体、WebView2 检查不碰注册表、`ctypes.windll` 不存在时 `_alert` 不二次崩。**这是"将来上 mac / 安卓"的基础**，
  但只验到"分支走得到且 fail-open"，真机没试过。
- 验收脚本自身的坑（顺手修）：`_check_exe_package.py` 会把探针串写进用户配置的 `window.title`，跑完不还原 →
  后跑的 `_check_exe_single.py` 按标题找窗口就找不到（假 FAIL）。现在收尾会把配置从 `config.yaml.bak` 还回去，
  `_check_exe_single.py` 也改成**从配置读期望标题**。

**产物**（`scripts/build_exe.ps1`，onedir **39.2 MB** / zip **20.1 MB**，构建约 26 秒）：
- `build_out/GuzhuComic/GuzhuComic.exe`（SHA256 `BF755DC1E738F1CF2162FC38C245F4D312972A17D1601078DF10C2EC3866B2B3`，7.19 MB）**← 已被下面的第三次出包取代**
- `build_out/GuzhuComic-0.1.0-win64.zip`（SHA256 `FED239FD89412F20862423B24BE59D81BC1E1A9BD9249B44D56144086D43D590`）**← 同上**
- `build_work/app.ico` 现在**真的有 256×256 那一帧**（16/24/32/48/64/128/180/256，实测读回没错）。

**打包态验收（真 exe，三份都全绿）**：
- `_check_exe_package.py`：窗口标题 `Guzhu Comic`、`:47753/index.html` 就是包内 dist、`/images` 同源取图 200（164 KB）、
  `webview/` 318 个文件、页面回报 `kids=1|rec=shown|cards=10|resume=shown|rows=30`。
- `_check_exe_real.py`：清掉 `config.yaml` 与 WebView2 用户数据后真首启 → 进程活着、标题对、`:47753` 正常、首启写出配置。
- `_check_exe_single.py`（6/6）：第一个起窗口 → 第二个弹「孤竹漫画已经在运行了」并 exit 0 → 第一个窗口原样还在。
- **日志在冻结态实测可用**（这次新加的，日志本身就是验收对象）：`~/.jmreader/logs/app.log` 里能看到 banner——
  `孤竹漫画启动：frozen=True python=3.14.6` / 配置路径 / 加载地址 / 窗口参数，接着是 jmcomic 的
  `【api.setting】change APP_VERSION from [2.1.7] to [2.1.11]`（topic 折进去了、**没有重复行、没有格式报错**）。
- **中文路径 / 中文用户名也验了**（`tmp/_check_exe_nonascii_path.py`，6/6）：同学把 zip 解压到「漫画 工具」这种带中文与空格的目录、
  以及 `C:\Users\张三` 这种中文用户目录（靠给子进程改 `USERPROFILE` 模拟）—— 窗口起得来、静态服务照喂 dist、
  首启把 `config.yaml` 与 `logs/app.log` 写进中文用户目录。这是"发给别人用"最容易被问到的场景，所以专门建了用例。
- 旧回归重跑全绿：`_check_hero_dedupe` / `_check_coldstart` / `_check_bridge_wipe` / `_check_nav` / `_check_history` /
  `_check_reader_sheet` / `_check_router_guard` / `_check_hardening` / `_check_imgserver` / `_check_api_smoke` /
  `_check_webview2` / `_check_webview2_gate` / `_check_single_instance`；`tsc && vite build` exit 0。

**Defender 复扫**：onedir / exe / zip 三处 `MpCmdRun -ScanType 3` 仍 **found no threats**。

**VirusTotal（75 引擎，走 `127.0.0.1:7890` 代理；上传即把样本共享给厂商，用户点头过）**：
- `GuzhuComic-0.1.0-win64.zip` → **0 / 75 报毒**（undetected 66、type-unsupported 7、timeout 2）——
  **发出去的就是这个包，用户拿到的判定是干净的**。
- `GuzhuComic.exe` → **2 / 75 报毒**，两家都是"行为启发式"而不是特征命中：
  `APEX: Malicious`（VT 上出了名的滥报）、`Skyhigh: BehavesLike.Win64.Backdoor.vc`
  （McAfee 那条云引擎，`BehavesLike` 是启发式命名，PyInstaller 打包的 Python 程序是它的常客）。
- **大厂全放行**：Microsoft / Kaspersky / ESET-NOD32 / BitDefender / Avast / AVG / Symantec / TrendMicro /
  Sophos / Fortinet / PaloAlto / Google / SentinelOne / CrowdStrike / Elastic / F-Secure / Malwarebytes。
- **国内杀软也全放行**（这是用户最关心的一条）：`huorong`(火绒) / `Tencent`(腾讯) / `Kingsoft`(金山) /
  `Rising`(瑞星) / `Alibaba` + `alibabacloud` / `Antiy-AVL`(安天) / `Jiangmin`(江民) / `Sangfor`(深信服) —— 全是 undetected。
- 原始报告留在 `tmp/_vt/*.json`（`*.full.json` 是逐引擎判定）。要不要为那两家启发式引擎提误报申诉：**用户定**（还没提）。

**踩到的坑（写给以后）**：
- Node 读写带 BOM 的文件要小心：`fs.readFileSync(p, 'utf8')` **不会**吃掉 BOM（它变成 `\uFEFF`），再自己补一个 BOM 就变成两个 →
  PowerShell 直接解析失败（`Unexpected token ')'`，报在注释块里，看着像内容坏了其实是 BOM）。改 `.ps1` 一律"先剥 BOM 再补一个"。
- `_check_exe_real.py` 会**删掉** `~/.jmreader/config.yaml` 与 `webview/`（它验的就是真首启）—— 跑它之前心里有数：
  阅读记录在 `data/app.db`（不动），但 localStorage 里的主题 / 偏好会回到默认。

### 第三次出包：文件名收口 + 运行足迹验收（2026-10-14，给同学用之前）
*(这一版的产物已被下面的第四次出包取代 —— 第三次之后又补了 Host 白名单)*

用户问："不会污染我朋友本机的 Python 环境、内外几乎隔离、安全性都有保障对吧" —— 这类话不能凭感觉答，
所以这一轮做的是**逐条去查**，查出一条真洞并堵上：

**查出来的洞：图片文件名来自图源，我们直接拿来拼路径**
- `img.filename` 是 jmcomic 从**图源页面里那个字符串**切出来的（`jm_entity.py` 的 `data_original[x+1:y]` 加后缀），
  也就是远端说了算；而 `api.py` 里有 6 处 `目录 / img.filename`（缓存预加载、整本下载各三处）。
  名字里带 `\\` 或 `..` 时，Windows 会把它当路径 → **图源（或它经过的 CDN）被投毒就能往下载 / 缓存目录外面写文件**。
  正常数据碰不到（实测 207 张全是 `00001.webp` 这种），但这是个真权限越界，代价又低，所以堵掉。
- 收口方式：新增 `_img_name(img)`——只取最后一段（`a/b/00001.webp` → `00001.webp`）；末尾是点/空格、
  带 `<>:"|?*` 或控制字符、是 `.`/`..`/空的，一律退回**按序号命名**（`00007.webp`，后缀尽量保住，
  因为 jmcomic 按后缀选解码方式、`.gif` 那条路跟别的图不一样）。6 处拼路径全走它，缓存里存的文件名也跟着变了。
- 回归：`tmp/_check_hardening.py` 新增「图片文件名收口」一组（正常名原样返回 / 正反斜杠穿越 / `..` / `...` /
  末尾空格 / 非法字符 / 控制字符 / 拼出来的路径必须还在目标目录里）；`tmp/_net_chapter_names.py` 拿真图源跑
  端到端（207 张、名字一个没改、缓存目录里落的就是 `00001.webp…`）。

**运行足迹：把"不污染本机"变成可复现的证据**（`tmp/_check_exe_footprint.py`，6/6）
- 做法：把包放进受控环境跑一次（假 `USERPROFILE` + 假 `TEMP`），前后 diff。
- 结果：新文件 **206 个，全部在 `<home>/.jmreader` 里**（config.yaml / data / cache / logs / webview 202 个）；
  `<home>` 下**没有别的落点**；假 `%TEMP%` **0 个新文件**（onedir 不解压）；**程序自己的目录 0 个新文件**
  （所以放只读位置也能跑）；注册表**没新增卸载项**、**没动 HKCU 的 PATH**。
- 局限：只对比了这几个能控制的目录，`%LOCALAPPDATA%` 里的 WebView2 运行时缓存之类没做全盘 diff。

**这一轮同时查过、没问题的**
- 本地服务只绑 `127.0.0.1`（`backend/server.py` 里是 `ThreadingHTTPServer(("127.0.0.1", candidate), ...)`），
  **不是 `0.0.0.0`** → 局域网里别人访问不到。`/images`、`/downloads` 两个静态根的路径穿越已有回归（`_check_imgserver.py`）。
- **Host 白名单**（这条是第三次出包**之后**才补的，见「第四次出包」）：`_QuietHandler._host_ok` 只认
  `127.0.0.1` / `localhost` / `[::1]`（带端口可以），其余 403 —— 不查这条的话 "DNS rebinding" 是通的：
  恶意页面把自己的域名解析到 127.0.0.1，浏览器就当成同源，于是能读走 `/images`、`/downloads`。
- 前端把图源返回的文本一律当不可信：`escapeHtml()` 进模板、`textContent` 兜底；封面地址单独把 `"` 转成 `%22`
  （它既要进 `src=""` 又要进 `style --cover: url("")`）。全库扫了一遍 `innerHTML` 里的插值，剩下没走转义的都是本地常量/布尔。
- 包内无遥测、无自动更新、无远程加载代码；只连图源站点（curl_cffi，HTTPS 校验证书）+ WebView2 加载本地 dist。

**产物（第三次）**
- `build_out/GuzhuComic/GuzhuComic.exe`（SHA256 `A733D6F622B03F83C9AC0A0681AF9A91421143D270A9E2678598CC85B3EC12C1`，7.02 MB）**← 已被第四次出包取代**
- `build_out/GuzhuComic-0.1.0-win64.zip`（SHA256 `5404CCED1DC910D38E05D20D958A74918A68E9F46D944F011BF1328F72182433`，20.1 MB）**← 同上**
- 验收：`_check_exe_package`（页面回报 `kids=1|rec=shown|cards=10|resume=shown|rows=30`）、`_check_exe_single`（6/6）、
  `_check_exe_nonascii_path`（6/6）、`_check_exe_footprint`（6/6）、`_check_hardening` / `_check_api_smoke` / `_check_imgserver` 全绿。
  **这一轮没跑 `_check_exe_real.py`** —— 它会清掉本机 `~/.jmreader/config.yaml` 与 `webview/`，
  而"真首启"这件事已经被 `_check_exe_footprint`（假用户目录）覆盖，就不必再动自己的数据。
- Defender：onedir / exe / zip 三处仍 **no threats**。VirusTotal（75 引擎）：**zip 0/75**（66 无检出 / 7 不支持 /
  2 超时；VT 把这个 zip 认成 "Python Wheel package"，因为它里头是一堆 `.py` + `dist-info` —— 不影响判定）；
  **裸 exe 2/75**，还是 `APEX` 与 `Skyhigh: BehavesLike.Win64.Backdoor.vc` 那两家行为启发式，与上一版判定完全一致；
  大厂（Microsoft / Kaspersky / ESET / BitDefender / Symantec / TrendMicro / Sophos / Fortinet / Google /
  CrowdStrike / SentinelOne …）与国内（火绒 / 腾讯 / 金山 / 瑞星 / 阿里 / 安天 / 江民 / 深信服）全部 clean。
  **注意**：zip 那种"容器判定干净"和"解压出来的 exe 判定"要分开看 —— 同学解压后落盘的是 exe，别人机器上的杀软看的是那个 exe。

**还没验的**（别当结论）：本机那个 WebView2 运行时缓存的落点（`%LOCALAPPDATA%`）没查；
同机"别的进程能读本地服务"这件事只做了代码级判断（`127.0.0.1` + 无鉴权），没写攻击用例去逼。
### 第四次出包（最终，发布版）：Host 白名单 + 打包态 Host 验收（2026-10-14）

第三次出包之后又补了一处加固 —— **本地静态服务的 Host 头只能是自己**（挡浏览器侧的 DNS rebinding），
所以重打了一次包。**这一版就是发给同学的那一版**。

- 代码：`backend/server.py::_QuietHandler._host_ok()` —— Host 只认 `127.0.0.1` / `localhost` / `[::1]`（`:端口` 可有可无），
  其余一律 403；`do_GET` / `do_HEAD` 各拦一道；不带 Host 的请求（HTTP/1.0 口径）放行。目录列表本来就禁着。
- 新增**打包态**用例 `tmp/_check_exe_host.py`（8/8）：拿**真 exe** 起的服务、换 `Host` 头打同一台机器 ——
  `127.0.0.1:47753` / `localhost:47753` / `[::1]:47753` → 200；`evil.test`、`127.0.0.1.evil.test`、`my.localhost` → 403
  （`/index.html` 与 `/images/…` 各打一次）；不带 Host → 200。**这也是"最后一次改动确实进了包"的唯一证据** ——
  包内模块压缩在 PYZ 里，grep 字符串搜不出来，只能功能验（第一版想靠搜字符串确认，白搜了两轮）。
- 时间戳也对得上：`backend/server.py` 18:35:42 改完 → 18:36:29 出包（`--clean` 全量重建）。
- 验收：`_check_exe_host`（8/8）、`_check_exe_package`（页面回报 `kids=1|rec=shown|cards=10|resume=shown|rows=30`）、
  `_check_exe_single`（6/6）、`_check_exe_nonascii_path`（6/6）、`_check_exe_footprint`（6/6）、
  `_check_hardening` / `_check_imgserver` / `_check_api_smoke` 全绿。
- Defender：onedir / exe / zip 三处仍 **no threats**。
- VirusTotal（75 引擎）：**zip 0/75**（64 无检出 / 7 不支持 / 3 失败 / 1 超时）；**裸 exe 3/75** ——
  `APEX: Malicious`、`Skyhigh: BehavesLike.Win64.Backdoor.vc`（这两家前两版也是它俩，判定一致）+ 这一版多的一家
  `Zillya: Trojan.Blank.Script.2228`（乌克兰小厂；报的名字里带 "Script" 而样本是 PE 二进制，属它那套启发式的口径，
  已触发一次重新分析复核，判定没变）。大厂（Microsoft / Kaspersky / ESET / BitDefender / Symantec / TrendMicro /
  Sophos / Fortinet / Palo Alto / Google / CrowdStrike / SentinelOne …）与国内（火绒 / 腾讯 / 金山 / 瑞星 / 阿里 /
  安天 / 江民 / 深信服）全 clean。
- **产物（最终）**：
  - `build_out/GuzhuComic/GuzhuComic.exe`（SHA256 `F9F472FEFF4BE9588CE70EC6E879203547D2D6162CE422F047EA331E88982ABF`，6.86 MiB）
  - `build_out/GuzhuComic-0.1.0-win64.zip`（SHA256 `EED8632782F017345FEAFCA60C3A97007C5648AFF6033ADAD5E58B09AED09C1E`，20.1 MB）
- **zip 与 exe 要分开看**：同学解压后落盘的是 exe，别人机器上的杀软看的是那个 exe（不是 zip）。分发时给 zip + 校验和。

### 直连可用性实测：**不需要科学上网**（2026-10-14）

用户问："这个 exe 没有科学上网环境能用吗？需要从 GitHub 下载东西吗？" —— 实测结论：

- **包本身完全自足**：Python 运行时 / jmcomic / curl_cffi / Pillow / pycryptodome / WebView2 的 .NET DLL / 前端 dist
  全在 `_internal` 里。运行时**不连 GitHub、不连 pypi、不下载任何东西**（jmcomic 那个 `get_html_domain_all_via_github`
  已废弃，源码里写着 "the GitHub repository no longer provides JMComic domains"，现在转发到站点自己那套）。
- **唯一的外部运行时是 WebView2 Runtime**（Win11、Win10 1803+ 基本自带），**不随包分发、也不自动下载**。
  真缺了只能用户手动装一次（微软官网）。除此之外零依赖：不需要 Node / Python / Vite。
- **抓图的网络请求，本机直连实测全通**（清空 `HTTP(S)_PROXY` + `NO_PROXY=*`，用应用自己的客户端 curl_cffi 模拟 Chrome）：
  `https://www.cdnhjk.net/setting` → 200；`/album?id=422866` → 成功；`/chapter?id=209828` → 成功、207 张（2.1s）；
  图片 `https://cdn-msp.jmapiproxy1.cc/media/photos/.../00001.webp` → 200 `image/webp` 172 KB（约 1s/张）。
  结论：**没有代理也能正常看**。
- **注意两点**：① 应用用的是 curl_cffi（Chrome 指纹），普通 urllib 直连会 TLS reset / 超时 —— 不是应用的问题；
  ② 站点域名与图床 CDN 会轮换，偶尔挑到不通的那个会重试或换域名（`api.update_domain.success` 那行日志就是它在换），
  已经缓存 / 下载到本地的那一话完全不受影响。
- 脚本：`tmp/_net_direct_test.py`（纯 TCP/TLS 探测）、`tmp/_net_jm_test.py direct|proxy`（A/B）、`tmp/_net_img_test.py`（真取图）。

## 健壮性审计（漏洞 / 崩溃点）改动清单（2026-10-14）

用户要求：**不再加功能，通读全库找漏洞和可能崩的地方，补掉，最后检验**。**还没打包**。

做法：先只读审查（前端 20 个 `.ts` + `backend/api.py` 全 1953 行 + `config.py` / `glass.py` / `main.py`），
按「整窗空白 → 静默丢数据 → 参数形状炸 → 信息暴露」排优先级；能复现的才动手，每改一处跑 `tsc` + `build`。

**前端**
- `frontend/src/router.ts`：`resolve()` 原来是**先清空 `#app` 再调 handler** —— handler 一抛就是整窗空白、连提示都没有
  （各页面自己的 try/catch 管的是它们**之后**的异步加载，管不到"挂载那一刻"）。现在 handler 包 try/catch，
  出错渲染 `renderError`（加载失败了 + 重试，重试就是再 `resolve()` 一次）；`#app` 找不到就返回，不把异常抛进事件回调。
- `frontend/src/main.ts`：`const boot = await loadSettings()` 挂在 `startRouter()` **前面**，一抛就永远开不出路由。
  `loadSettings` 内部虽然 catch 了读配置失败，但"桥调用被清掉/超时"抛的是普通 Error → 顶层 await reject。
  改成 try/catch + 回落 `DEFAULT_SETTINGS`（这是"整窗空白"的第三个入口，前两个是桥注入清回调、`bridgeCall` 没接住）。
- `frontend/src/pages/board.ts`：`scheduleRetry` / 各横条的重试定时器可能在**切页之后**才醒 → 对着已经拆掉的面板再打一轮桥。
  加 `dead` 标志（`onUnmount` 置位），`load()` 与横条重试都先看它。
- `frontend/src/pages/reader.ts`：`armRetry` 那段缩进是错的（功能对，但 4 / 8 空格混着写，读起来像有 bug）—— 只重排缩进。
- `frontend/src/pages/downloads.ts`：`get_downloads()` 的返回值直接当数组用；形状不对会在 `tasks.some/map` 上抛一个
  没人接的 rejection，整页停在骨架。加 `Array.isArray` 兜一道。

**后端（`backend/api.py` / `backend/config.py`）**
- `config.load_config()`：读不动 / YAML 写坏 / 顶层不是映射 / 某一段被写成标量（`window: 5`）→ 一律回落默认值。
  这是**开窗路径**上的函数，抛出去 = 窗口起不来（以前手改坏 `config.yaml` 就是一句 Python traceback）。
- `save_settings()`：原来只 catch `ValueError`，而 `settings.get("window") or {}` 碰上非映射会抛 `TypeError` **原样直穿 JS 桥**。
  新增 `_setting_section()`（非映射当场报「窗口那一段要是一个小节」），`except` 放宽到 `(ValueError, TypeError)`，
  `save_config` 写盘失败也包成「保存失败：config.yaml 写不进去（…）」。
- `save_progress()`：`int(page_index)` 无校验、`title/cover_url` 原样进 SQL（那两列是 NOT NULL）——
  脏入参会抛 `IntegrityError`，**这一话的真实进度反而丢了**。现在页码夹到 ≥0、文本一律 `str(...)`。
- `get_history()`：`int(limit)` 不夹范围，而 sqlite 里**负数 LIMIT = 不限制**（等于绕过上限）→ `_cfg_int(limit, 10, 1, 500)`。
- 缓存形状：`_cache_get` 对坏 JSON / 非数字 `fetched_at` 判成"没命中"；新增 `_cache_list()` 只认 list 形状，
  用在 `get_chapter` / `_download_chapter_to_dir` / `prefetch_chapter` / `search` / `get_ranking`；
  详情 / 评论 / 论坛三处缓存加 `isinstance(dict)`。以前缓存里塞进别的形状会以 `TypeError` 直穿 JS 桥。
- `start_download()`：`chapters` 不是 list/tuple 时 `for` 出来的全是垃圾（传数字直接 TypeError）→ 提前报「话单要传列表」。
- `get_recommendations()`：`exclude` 不是可迭代就当没传，别为一个参数形状把整段推荐打掉。
- `cleanup_cache()`：算目录 mtime 时 `.stat()` 可能撞上下载线程改名 / 删文件 → 这一趟不参与排序，不再让整次清理失败。
- 本地图片服务 `_QuietHandler`：**关掉目录列表**（`list_directory` → 403）。服务只监听 127.0.0.1 + 随机端口，
  但 `/images/` `/downloads/` 列目录等于把缓存与离线副本的结构摊开给本机任何程序看。
- 顺手统一连接：`sqlite3.connect(...)` → `_db(...)`（35 处），**只改一处行为**：等锁上限 5s → 15s
  （整本下载逐话写库、界面同时存进度时 5 秒偶尔不够）。`with sqlite3.connect()` 只提交不关连接这点保持原样
  （CPython 靠引用计数在函数返回时回收，实测没有句柄残留），**没做大规模重构**。

**验收（全部 exit 0）**
- `tsc --noEmit` + `npm run build`；`python -m py_compile` 四个后端文件；`tmp/_check_history.py`（真库）正常。
- 新增 `tmp/_check_hardening.py`（**5/5 PASS**）：坏 `config.yaml` 六种写法、`save_settings` 七种非法入参 + 写盘失败、
  缓存坏 JSON / 错形状 / 错 `fetched_at`、`save_progress` 脏页码与 None 文本、`get_history` 五种非法 limit、
  `start_download` / `get_recommendations` 非法入参 —— 全跑在临时库 + 假 self 上，不碰真 `data/` / `cache/` / `config.yaml`。
- 新增 `tmp/_check_router_guard.py`（无头 Chrome + 假桥）：**先把 `aboutPage()` 临时改成直接 throw**，再 build 跑一遍 ——
  `#app` 里出现「加载失败了 + 重试」而不是空白、点重试仍在、切到 `#/popular` 首页照常（**ALL PASS**）；
  还原 `about.ts`（`git diff` 与还原前一致，逐字节核对过行尾）后 normal 模式也 ALL PASS。
- 新增 `tmp/_check_imgserver.py`（**3/3 PASS**）：目录列表 403、正常取图 200、六种路径穿越都拿不到根目录外的文件。
- 新增 `tmp/_check_api_smoke.py`：真库上把改到的读接口各跑一遍（`get_settings` 九段齐全、`get_history(60)`→2 条、
  `get_downloads` / `get_favorites` / `get_search_log` / `get_cache_stats` / `get_taste_profile` / `get_album_progress` 全正常）。
- 老回归全绿：`_check_hero_dedupe.py` / `_check_coldstart.py` / `_check_bridge_wipe.py` / `_check_nav.py` /
  `_check_reader_sheet.py`（ALL PASS）。
- 真窗口探针 `tmp/_probe_bridge.py`：`dev`（vite 5173）与 `--dist` 各一趟，`returnValueFAIL=[]`、`missingApi=[]`、
  `appKids=1`、`rec=shown` + `recCards=10`、`resume=shown`、`heroVsBelow={hero:3,dup:[]}`；
  dev 那趟正好抓到两遍注入（1184ms / 1240ms，间隔 56ms）也**零失败**。


## 首页 hero 去重 改动清单（2026-10-14）

用户要求：**hero 展示的漫画不要在下面再出现一次**。首页 DOM 顺序是 hero → 面板（推荐段 → 各分类横条），
所以"下面"这两块都要去重。**还没打包**。

- `frontend/src/pages/board.ts`：
  - 新增 `dropHero(items)`：在**取回来的整页里**先剔掉 hero 那几部、再切前 `--cols` 张
    （切完再过滤的话横条会短一截，看着像少了一部；多出来的候选正好补上空位）。`fillRow()` 统一走它，
    所以 `paintRow()` 与 `warmVisible()`（预热）看到的是同一份名单。
  - 推荐段建起来时把 hero 的 ID 透过去：`createRecommendSection('home', () => heroIds)`；
    `rec?.load()` **从"开始加载就调"挪到 hero 落定之后**（拿到那三部才有得避开），
    hero 挂了（`renderHeroError` 那条路）也照常调一次 —— 没有要避开的 ID，不能连它一起没了。
- `frontend/src/components/recommend.ts`：`createRecommendSection(kind, shownAbove?)` ——
  `shownAbove()` 返回"页面上方已经展示过的 ID"，跟内部 `shown`（「换一批」用的）**并起来**当
  `get_recommendations` 的 `exclude`。后端是在**打分之前**剔候选的，所以去重不掉张数。
- **验收**：`tsc --noEmit` + `npm run build` exit 0；新回归 `tmp/_check_hero_dedupe.py`
  （无头 Chrome + 假桥，故意喂重叠榜单：hero 取 H1/H2/H3，同人那一行前三部也正好是 H1/H2/H3）
  **PASS** —— hero = H1/H2/H3、五条横条一个 H 都没有且同人那行**没被削短**（D4…D8 五张，跟别的行一样）、
  推荐段收到的 `exclude` 正好是 H1/H2/H3、铺出来的卡里没有 H。
  **反向对照**：把 `dropHero` 的 skip 集合临时置空 + 去掉 `shownAbove` 再 build 一份，同一脚本
  FAIL（同人横条出现 H2/H1/H3、推荐段 `exclude` 为空、推荐卡里出现 H1/H2/H3）—— 证明这个脚本抓得住。
  真窗口 `tmp/_probe_bridge.py` 也加了一项 `heroVsBelow`：真图源跑两趟都是 `{hero: 3, dup: []}`。
  其余回归 `_check_coldstart.py` / `_check_bridge_wipe.py` / `_check_nav.py` 全 PASS。

## 首进首页「整窗空白」：闸门按方法引用判重注入 改动清单（2026-10-14）

接上一轮的根因修复（后端 `_jm` / `_download_dir` 改名 + `waitForBridge` + `bridgeCall`）。这一轮做**真窗口复测**，
发现闸门的「安静窗」还有一个漏洞，顺手补掉。**没打包**（用户说还要加东西）。

- **漏洞**：`readyStamp` 原来只由 `pywebviewready` 刷新。真机上遇到过桥比我们的脚本先挂好 ——
  事件早派发完了、`readyStamp` 停在 0 → `Date.now() - 0` 恒大于 `quietMs` → **闸门当场放行**，
  正好撞上第二遍注入（那一次 3 个在飞调用被清）。探针那次实测：注入 1128ms / 1250ms，而首个调用 1248ms。
- **改法**：`webstatus.ts` 换成**按方法引用变化**判重注入（`noteMount()`）——`_createApi()` 每跑一遍都是
  `new Function()` 现造一套函数，引用变了就是又注了一遍，不依赖事件、漏不掉。`quietMs` 400 → 800
  （探针实测两遍注入最多差 ~400ms；多等这点不花成本，闪屏本来要等 `splashReady` 才揭幕）。
- **验收**：`tsc --noEmit` + `npm run build` exit 0；真窗口探针 `tmp/_probe_bridge.py`（自己起真 pywebview，
  三路仪器：注入次数与时刻 / 后端被调到的时刻 / `evaluate_js` 送返回值有没有炸）——`dev`（vite 5173）×3 +
  `--dist`（另起静态服务喂 `frontend/dist`，打包后的样子）×2，**5/5 全绿**：`appKids=1`、`rec=shown`、
  `recCards=10`、`resume=shown`、`returnValueFAIL=[]`。其中一次刚好抓到「注两遍」（间隔 59ms）：**零失败**。
  无头回归 `tmp/_check_coldstart.py` / `tmp/_check_bridge_wipe.py` / `tmp/_check_nav.py` 全 PASS。

## 阅读器浮层：点外面就关 改动清单（2026-10-14）

用户报：阅读页开着的设置 / 章节目录，点面板外面的地方应该只是把它关掉。

- `frontend/src/pages/reader.ts`：
  - 图片区的 `click` handler 开头加 `if (sheetOpen()) { openSheet(null); return }` —— 这一下只用来收面板，不再顺手翻页 / 收工具条；
  - 新增 `onOutsideClick`（挂 `document`，冒泡期，`onUnmount` 解绑）：面板开着且点击目标不在 `.reader-sheet` / `.chapters-btn` / `.settings-btn` 里 → `openSheet(null)`。两个开关按钮必须放过，否则「目录 → 设置」会先切成设置、再被判成"点了外面"立刻关掉；
  - `onWheelFlip` 加 `sheetOpen()` 短路：单页模式下滚设置面板 / 目录，底下那页会跟着翻。
- 验收：`tsc --noEmit` + `npm run build` exit 0；`tmp/_check_reader_sheet.py`（无头 Chrome + 假桥，10 步点击序列 **ALL PASS**：开→点图片区关→切面板不被误关→点留白关）；截图 `tmp/_ui/v9-reader-{chapters,settings}.png`。
## 左下角「继续阅读」+ README 亮点 改动清单（2026-10-14）

用户要两件事：**左下角加一个「继续阅读」按钮**（显示最近阅读里时间最近的那本，上面渲染卡片）+ **把项目亮点写到 README 最显眼的位置**。
**还是没打包**。用户没点具体条目，按对他最有利的挑了：数据不出本地 / 能反复读 / 接着上次看 / 推荐真算 / 无广告无账号 / 现代桌面壳 / 坏一格不连累整页 / 离线优先。

- `frontend/src/resume.ts`（新）：`createResume()` → `{el, refresh}`。卡片（封面 + 两行标题 + 读到第 N 页）和按钮都指向 `#/read?photo_id=&album_id=`（阅读器自己会落回上次那页）；`get_history(1)` 拿第一条，`loading` 标志挡并发，拿不到就保留上一次、首次失败保持隐藏。
- `frontend/src/main.ts`：`prepend` 到 `.nav-foot`（在关于 / 设置上面）；桥就绪后 `refresh()` 一次，之后每次 `hashchange` 再刷一次。
- `frontend/src/style.css`：`.nav-resume` / `#nav .resume-card` / `.resume-cover` / `.nav-resume-go`（跟主题开关共用一套按钮外观，顺便把 `<button>` 被 UA 锁成居中的内容改成靠左）；窄屏藏卡片、按钮只留图标。
- `README.md`：新增 `## 亮点` 段（放在页首、正文第一件事），页面表补「关于」路由，左侧导航那条补「继续阅读」。
- 验收：`tsc --noEmit` + `npm run build` exit 0；无头 Chrome 截图（`tmp/_ui/v8-*.png`：有记录 / 无记录 / 窄屏 / 浅色）+ 点按钮读 `location.hash` 的功能核对（`tmp/_check_nav.py`）。
- 踩到的坑（都写进 `tmp/交接文档.md` §5.16）：`display:flex` 盖掉 `hidden` 的 UA 规则、`<button>` 内容被 UA 居中、`#nav a` 权重压过 `.resume-card`、`a.href` 是绝对地址不能当 hash 用。
## 导航左下角（关于 / 设置）改动清单（2026-10-14）

用户要两件事：**「设置」挪到左侧导航栏左下角** + **在它旁边加「关于」**，点开是一页 README 的精简版。
**还没打包** —— 用户明确说"先不打包，还要加别的东西"。

- `frontend/src/main.ts`：`NAV_ITEMS` 只留内容导航那 6 项（热门 / 搜索 / 论坛 / 最近阅读 / 收藏 / 我的下载）；
  新增 `NAV_FOOT_ITEMS`（关于 / 设置）挂到 `.nav-foot-row`，主题开关改挂 `.nav-foot`（`margin-top: auto` 跟着挪到容器上）；
  `syncNav()` 改成走 `navLinks` / `navIcons` 两张 Map（分两排后按 `a[data-path]` 找会漏）；注册 `#/about`。
- `frontend/src/pages/about.ts`（新）：**纯静态**一页，不发请求、不引 `settings.ts` 那套表单；三块内容（能干什么 / 怎么用 / 数据都在本机）+ 复用 `.about-card` 那套页脚。
  **故意不放外部链接**：这个壳没做 `target=_blank` / `webbrowser`，点出去会把当前页顶掉。
- `frontend/src/style.css`：`.nav-foot`（顶到底 + 一条发丝线）、`.nav-foot-row`（两个入口平分一行）、`.about-*` 一组；
  窄屏（≤1180px）除了 `.nav-foot-row` 竖排，还要 `.nav-theme span { display: none }` —— 原来只藏 `#nav a span`，
  主题开关的标签是 `<span>` 不在那条规则里，「深/色」会在 64px 里竖着折行把导航栏顶破（按钮加了 `title` 兜底）。
- `frontend/src/components/icons.ts`：`about: Info` / `aboutOn: BadgeInfo`。
- 验收：`tsc --noEmit` 与 `npm run build` exit 0；无头 Chrome 截图核对暗色 / 浅色 / 窄屏（`tmp/_ui/v7-*.png`），导航 8 个入口 = 6 + 2，底部一对在窄屏正常竖排。

## UI 动效 / 材质 + 双主题 改动清单（2026-10-14）

用户要的是"一套 UI 动效与质感"，六条：全局动效变量、主题切换的圆形揭示、统一加载签名、封面 → 阅读器共享元素转场、
卡片/按钮材质、空状态与骨架屏网点化。约束：只动画 `transform` / `opacity`、要 `prefers-reduced-motion` 降级、桌面 WebView2。
**只改 `style.css` + 少量 HTML/TS，没碰业务逻辑。**

- `frontend/src/style.css`（主要改动）
  - `--ease-spring` / `--ease-out` / `--dur-*` / `--depth-1` / `--depth-2` / `--edge` / `--edge-strong` / `--dots` / `--dots-ink` / `--tint` / `--ring` / `--glass-*`；
  - `button { transition: transform … ; box-shadow: var(--edge) }` + `button:active { transform: scale(.96) }`；`album-card` 多层材质 + hover 抬升 + `:active`；
  - 空状态整段重写成漫画气泡（网点底 + 左下角尾巴）；骨架屏全部改网点 + `ink-flow` / `sk-breathe`（只动 transform / opacity），删掉旧的光带；
  - 新增 `.paper-grain`（SVG feTurbulence 噪点纸纹，fixed / `z-index: -1` / `pointer-events: none`，`body.reading` 时 0.42）、
    `.reader-images:empty::before`（章节加载签名）、`.nav-theme`（导航底部的主题开关）、
    `:root[data-theme="light"]` + `[data-glass="on"]` 两套浅色变量、`[data-vt="reveal"]` 那组转场规则；
  - 文件末尾的 `@media (prefers-reduced-motion: reduce)` 段扩写：停掉所有加载动画、过渡清零、转场时长压到 1ms。
- `frontend/src/motion.ts`（新）`calmMotion()` / `themedReveal()` / `morphToReader()`；`theme.ts`（新）`currentTheme()` / `setTheme()`。
- `frontend/index.html`：第一帧之前定主题的内联脚本；闪屏里那条 14 点"网点墨水"进度条（内联 CSS，因为 style.css 还没到）；`.paper-grain` 那一层。
- `frontend/src/main.ts`：导航底部加主题开关；`components/icons.ts` 加 `Moon` / `Sun`；`pages/detail.ts` 两处进阅读器改走 `morphToReader`；
  `pages/reader.ts` 阅读设置浮层加「界面主题」。
- 验收：`tsc --noEmit` 与 `npm run build` 均 exit 0；无头 Chrome 12 个场景探针全绿（暗/浅主题配色与落盘、`data-vt` 挂摘、
  两处 `view-transition-name` 挂摘、章节跳转 + `.reading`、纸纹 SVG 解码 160×160、卡片/按钮/骨架/空状态的 computed style、reduced-motion 降级）。
  截图见 `tmp/_ui/v6-*.png`。
- **已知限制**：View Transition 的两段动画在无头 `--virtual-time-budget` 下回调不触发（实测），只能在真机上眼看；详见 `tmp/交接文档.md` §5.14。

## 整本下载（B3）+ 详情页文字不透明 改动清单（2026-10-14）

用户要的两件事：**下载**（左侧导航加「我的下载」、详情页「下载」跟「继续阅读」同一排、进度跟「最近阅读」一个口径、
断了下按进度接着下、下载地址进配置）+ **详情页的标签 / 作者 / 观看收藏数做成不透明的**。

设计稿：`tmp/下载设计.md`（§1 需求拆解、§7 缓存红线）。

- **配置组 `download`**：`workers`（原有）+ `dir`（离线副本目录，默认 `~/.jmreader/downloads`，支持 `~` 与相对路径）、
  `retries`（单张图重试次数，默认 3）、`auto_resume`（开窗自动续传，默认开）。5 处同步齐（`config.py` / `config.yaml` /
  `settings.ts` / `settings.ts` 的 GROUPS / `save_settings` 白名单；白名单里还会当场 `mkdir` 一次，路径写错立刻能说清）。
- **数据（`data/app.db`，用户数据）**：`download_album`（`album_id` 主键 + title / cover_url / total / done / state /
  error / added_at / updated_at）、`download_chapter`（**`(album_id, photo_id)` 主键** + index_no / title / state /
  total / done / updated_at，另加 `photo_id` 索引给阅读器反查本子）。**进程里不留计数** —— 进度就是磁盘上的文件。
- **磁盘**：`<download.dir>/<album_id>/<photo_id>/<文件名>`。**不放 `cache/`**：`clear_cache` / `cleanup_cache`
  只碰 cache，离线副本永远不被清理（用户数据红线）。
- **图片服务挂两个根**：`/images/...` → `cache/images`、`/downloads/...` → `download.dir`（`_QuietHandler.extra_roots`
  + `translate_path`，路径片段里的 `..` 一律丢掉）。`get_chapter` 有离线副本就整话返回 `/downloads/...`，
  **顺带不再往 cache 里下第二遍**；没有就维持原样。阅读器零改动。
- **断线重连 / 按进度重下**：`_download_chapter_to_dir` 先看 `photo:<id>` 缓存里的文件名（续传时下过的话一次网络请求都不发），
  再把缺的挑出来 `_download_images_batched` 一批批下（每张先 `.part` 再 rename）；单张失败重试 `retries` 次，
  还是失败只把那一话标 `error`、整本继续；一话标了 done 但磁盘上缺图也能被 `_pending_chapters` 量出来补回来。
  开窗 5 秒后 `_resume_downloads_loop` 把 `queued` / `running`（= 上次被关窗打死的）重新排队。
- **任务控制**：`pause_download`（批间停，已下的都留着）/ `resume_download` / `remove_download(album_id, delete_files)`
  （先叫停，最多等 5 秒，等不到也照删记录）。
- **新接口 6 个**：`start_download`（话单直接用详情页那份，省一次往返）、`get_downloads`、`get_download`、
  `pause_download`、`resume_download`、`remove_download`；任务对象里带 **`read`**（现拼 `history` 那行）——
  这就是"下载后的进度跟最近阅读里的一样"：同一个口径，同一张表。
- **前端**：
  - 左侧导航加「我的下载」（图标 `Download` / 高亮 `HardDriveDownload`），路由 `#/downloads` → `pages/downloads.ts`。
  - 详情页把「阅读」和「下载」包进 `.detail-actions`（同一排，阅读占大头）；下载按钮标签跟状态走
    （`下载` → `下载中 3/12 话` → `继续下载` → `已下载`），只在详情页开着且任务在跑时 2 秒轮一次（`onUnmount` 停表）。
  - 我的下载页：卡片副标题 `已下载 3/12 话 · 读到第 5 页`、封面右上角进度角标（下完的不留角标）、卡片下面
    「暂停 / 继续」+「删除」；有任务在跑时 1.5 秒轮一次，**任务集合没变就只改文字**（不重建 DOM）。
- **详情页文字不透明**：标题 / 作者 / 观看收藏评论数 / 标签各垫一层**写死颜色**的实色底（`#07080a` / `#141516`），
  不用 `--bg` 那套变量 —— 毛玻璃开着时变量本身是半透明的，拿它垫等于没垫。

## 整本下载 验证记录（2026-10-14）

后端（临时目录 + 假图源客户端，`tmp/_t_dl.py`，**42/42 通过**）：

- 未下载的章节走 `/images/`；`start_download` 立刻返回任务，整本下完 `state=done`、进度 `2/2 话`、张数 `8/8`。
- 下完的章节：`get_chapter` 返回 `/downloads/900/900-p1/...`，**不再下第二遍**（`img_calls` 没变）、
  cache 目录里也没多出文件。
- 图片服务真能取到离线副本（HTTP 200 + 内容对得上）；`/downloads/../../config.yaml` 这种穿越请求 404。
- **断点续传**：磁盘上已有 2 张时续传**只补缺的 2 张**、话单只拉 1 次（`get_photo_detail` 只调 1 次）。
- 一话彻底失败 → 整本 `state=error`、其它话照下（`2/3`）、失败那话留在 `error` 上；补下后 `3/3 done`。
- 暂停：`state=paused` 且确实没下完；继续后 `4/4 done`（不是从零重下）。
- 删除：任务行没了、`downloads/<album_id>` 目录也没了、该话的阅读又回落到 `/images/`。
- **开窗自动续传**：把某个 done 的话里删掉一张图 + 状态改成 `running` → 新开一个 API 实例（`auto_resume=true`），
  5 秒后自动把那**一张**补回来（磁盘量得出缺图，不靠内存计数）。
- **边下边补**：任务还在跑的时候再 `start_download` 补两话，新话下一圈就被捞上来，最后 `4/4 done`。
- `get_downloads` 的 `read` 跟 `get_album_progress` 同源；多任务按更新时间倒序；配置相对路径按 `~/.jmreader` 解析、
  空值回落 `downloads/`；`save_settings` 能存 `dir` / `retries` / `auto_resume`，越界与空目录都报错。

真图源冒烟（`tmp/_smoke_dl.py`，跑的是周榜第一部 `287234`）：

- 第一话 35 张图 15.1 秒下完，`state=done`、`35/35`；离线副本落在 `downloads/287234/287234/00001.webp...`；
  阅读地址变成 `/downloads/...`，HTTP 取回 79722 字节、头部 `RIFF`（真 webp）；`cache/images` 里 0 张；
  删除后目录不在了。

前端（无头 Chrome + 假桥，**23/23 通过**，截图核对）：

- 导航里有「我的下载」（`#/downloads`）；详情页 `.detail-actions` 里「阅读」和「下载」顶边齐、下载在右边。
- 下载按钮按状态显示「下载中 3/12 话」；点一下就带 2 话的话单调 `start_download`，标签立刻变「下载中 0/2 话」。
- 详情页 Title / meta / tag 的 `background-color` 分别是 `rgb(7,8,10)` / `rgb(7,8,10)` / `rgb(20,21,22)`（都是实色），
  且 `display: inline-block`（底板只包住文字）。截图里背后那层虚化封面被实色底挡干净了。
- 我的下载页：副标题 `下载中 0/2 话 · 读到第 5 页`、`已下载 8 话`；只有没下完的卡片有「下载中 x%」角标；
  点「暂停」→ 按钮变「继续」+ 角标变「已暂停」；点「删除」→ 调 `remove_download(id, true)`、卡片少一张；
  全删光显示空状态「还没有下载」。
- `tsc --noEmit`、`npm run build`（CSS 31.81 kB / JS 96.50 kB）、`py_compile` 全 exit 0。
- 没验的：真窗口（5173 + `main.py`）里的手感 —— 整本下载的真实速度、关窗打断后再开窗的续传观感，交给用户。

## 推荐算法一期 改动清单（2026-10-14）

用户要的：按**搜索与收藏的 tag** 做算法推荐，落在**首页与搜索页**，每次按热度拉前几部再算法匹配；搜索记录搬进数据库；收藏的**到处打角标**、没收藏的不留空位。

设计稿：`tmp/推荐算法设计.md`（v2 设计 + §14 落地偏差）。

- **搜索记录搬进 `data/app.db`**（原来是 localStorage）：新表 `search_log(keyword PRIMARY KEY, scope, hits, at)`，加 `log_search` / `get_search_log` / `remove_search_log` / `clear_search_log` 四个 js_api。同一个词（`COLLATE NOCASE`）只留一行、`hits` 累加、时间刷最新；表最多留 200 条。搜索页 chips 改读库，进页面时顺手删掉老键 `guzhu:search:recent`。
- **收藏快照**：`favorite` 表加 `tags_json` / `authors_json`（`_ensure_columns()` 用 `ALTER TABLE ... ADD COLUMN` 兼容老库）；`toggle_favorite` 多收两个参数（详情页把手里的 tags / authors 传过来）；老行缺快照先回落详情缓存，`get_album_detail` 拉新数据时 `_backfill_favorite` 补上。
- **画像** `_taste_profile()`：收藏（tag / 作者各 +1.0）+ 搜索（每词 0.6 × 次数），按 `recommend.half_life_days`（30 天）半衰、归一化、只留 top 20 tag + top 10 作者；每次现算、不落盘。搜索关键词同时当 tag 与作者字符串参与匹配。**隐式反馈不做**（用户砍掉）。
- **候选池** `_candidate_pool()`：周榜「全部」按观看前 `recommend.candidates`（40）部，走的就是 `ranking:*` 缓存；凑不满再要一页（最多三页）。
- **打分**：`score = (1 - hot_weight) · 匹配 + hot_weight · 热度`，`匹配 = (Σtag命中 + author_boost · Σ作者命中) / sqrt(1 + |tags|)`；候选的 tag / 作者**只读本地详情缓存**，没缓存算 0 分 —— 这条路上不发请求。
- **新接口**：`get_recommendations(kind, limit=None, exclude=[]) -> {cold, items:[{id,title,cover_url,subtitle,favorited,score}]}`（`cold` = 画像空或一个都没命中 → 标题写「热门推荐」）、`get_taste_profile()`（调试用）。
- **收藏态现拼**：`search` / `get_ranking` / `get_forum` / `get_favorites` / `get_recommendations` 的返回项统一带 `favorited`，**不进缓存**（跟现拼封面一个路子）。
- **新配置组 `recommend`**（5 处同步齐）：`limit 10` / `candidates 40` / `hot_weight 0.3` / `author_boost 1.5` / `half_life_days 30`。
- **前端**：
  - 新组件 `components/recommend.ts`（`createRecommendSection('home' | 'search')`）：骨架 → 卡片（副标题写命中原因）→ 行头「换一批」（把已展示的 ID 当 `exclude`）；失败 / 空 / `limit=0` 一律整段 `hidden`，不报错。
  - 首页：推荐段插在面板里 `boardMsgEl` 之后、分类横条之前（**第一段**），一行跟分类横条一样吃 `--cols`。
  - 搜索页：推荐段铺在结果列表下面（空状态时也在）；一期两个位置结果完全一致。
  - `album-card` 加「已收藏」角标（只有 `favorited` 为真才建 DOM）；论坛封面条上加小角标（贴标题行右端）；收藏页补 `warmAlbumList` 预热；收藏页与详情页不打角标。
  - 搜索页 chips 改读库：点 chip 重搜、✕ 删单条、清空，都落到库里。

## 推荐算法一期 验证记录（2026-10-14）

后端（临时 `data/` + `cache/` + 假图源，不联网、不碰真库）：30 项断言全过。

- 搜索记录：去重（不分大小写）/ 次数累加 / 删单条 / 清空。
- 收藏快照：`tags_json` / `authors_json` 落库。
- 收藏态现拼：榜单带 `favorited`；**走缓存那一次照样带最新收藏态**；取消收藏后立刻掉角标；`search` / `get_forum` 同样带。
- 画像：tag = 收藏的 tag + 搜索词；作者维度同样吃搜索词；归一化（最重 = 1.0、搜索词 0.6）；`favorites` / `searches` 计数。
- 打分：命中画像的排在池内最热的之前；名次挨着的两部里作者命中 > tag 命中；`exclude` 生效且顶上来的仍是命中画像的；副标题 = 命中原因（最多两项）。
- 冷启动：清空收藏 + 搜索 → `cold=True` 且就是热度前 N；`limit=0` 返回空；没缓存的候选不吃 tag 分（也不发请求）；候选池最多多要一页。

前端（无头 Chrome + 假桥）：首页 18 项 + 搜索页 12 项断言全过。

- 首页：推荐段是面板里第一段（在分类横条之前）、可见、标题「为你推荐」；3 张卡；只有已收藏那张有「已收藏」角标；副标题 = 命中原因，没命中就不显示；分类横条里同样只有收藏的那张带角标，**没收藏的卡片连空位都没有**（子节点数不变）。
- 「换一批」：`exclude` = 已展示的 ID；换完是新一批；两批都触发了 `prefetch_albums` 预热。
- 搜索页：chips 读的是库里那份记录（`get_search_log(12)`）；推荐段在结果列表下面；**冷启动标题变成「热门推荐」**；点 chip 用当前范围重搜并 `log_search`；结果里已收藏的那张带角标；✕ / 清空分别打到 `remove_search_log` / `clear_search_log`。
- 降级：推荐接口抛错、返回空这两种情况，**整段 `hidden`**（页面上不出现、也不报错），分类横条照铺。
- 截图看过：首页第一段的版式与角标位置、搜索页 chips + 空状态 + 推荐段。

`tsc --noEmit` / `npm run build` / `py_compile backend/api.py backend/config.py` 全部 exit 0。

## 推荐段"没了"核对（2026-10-14）

- 结论：**不是 bug**。真桥探针（`tmp/_probe_app.py`）实测首页 `.rec-section` 在、`hidden=false`、10 张卡，标题「热门推荐」；后端 `get_recommendations('home')` → `cold=True, items=10`。
- 为什么是「热门推荐」：画像空（`favorite` 0 行 / `search_log` 0 行）→ `cold=True`，按设计退化成热度榜；此时排序与周榜「全部·按观看」前 10 逐位相同，所以看着像普通热门榜。
- 有收藏 / 搜索后标题自动变「为你推荐」（副标题出命中 tag / 作者）。
- 遗留：`recommend.ts` 的 `load()` 一次性、失败不重试（hero / 分类横条都会重试），这是"推荐段真会消失"的唯一路径，**未修**。
- 详见 `tmp/交接文档.md` §5.15。

## 缓存策略 / 预加载 改动清单（2026-10-14）

用户要的：列表先铺封面 + 标题、详情随后；进详情页先下"要读那一话"的前几张；一话看到 90% 就预加载下一话。

- 新增配置组 `prefetch`（按纪律一次同步 5 处：`backend/config.py`、`config.yaml`、`settings.ts`、设置页 `GROUPS`、`save_settings()` 白名单）：
  - `prefetch.albums`（默认 12，0 = 关）：列表铺完后**每次**最多排队预热几部的详情。
  - `prefetch.chapter_images`（默认 3，0 = 关）：预加载时先下这一话的开头几张。
  - `prefetch.next_at`（默认 0.9，0 = 关）：一话看到这个比例就预加载下一话（前端读，滚动的事只有前端知道）。
- 后端两个新 js_api，**都立刻返回**，真正的活在后台 daemon 线程里（桥上的调用排在用户点击前面，预热不能占着它）：
  - `prefetch_albums(album_ids)` → 预热详情缓存（`album:v2:` 那套）。这次开窗期间认过的 ID 不再要；失败的**不记账**、下次进页面再试；一次最多 `prefetch.albums` 部。
  - `prefetch_chapter(photo_id)` → 下这一话开头 `prefetch.chapter_images` 张，返回要下的张数。**开头那几张已经在磁盘上就直接返回 0**（"之前看过就不用预加载"）。
- `_spawn_download` / `_run_download` 加 `limit`（只下前几张）和 `_dl_pending`：预加载那种"只下几张"的批次在跑时，用户真进阅读器要**整话**的请求必须记一笔，等这批跑完补一次 —— 否则那次请求被静默吃掉，缺的图永远下不来（页面上一直转圈重试）。清理缓存也把 `_dl_pending` 算进"绝对不能删"。
- `_run_download` 取完图列表顺手写 `photo:<id>` 缓存（`get_chapter` 也是这么写的），预加载才有依据判断"开头几张在不在磁盘上"，不用每次去网络问一遍。
- 前端新增 `frontend/src/prefetch.ts`（`warmAlbumList` / `warmChapterStart`：失败、桥没就绪、后端没这个方法一律咽掉），四个挂钩：
  - 首页 / 分类页（`board.ts`）：hero 回来、每个分类横条铺好、分类页翻页之后，把**真铺出来的**那些（hero 3 部 + 各行前 `--cols` 张 + 分类页已铺的）送进 `prefetch_albums`。
  - 搜索页（`search.ts`）：出结果后送这一页的 ID。
  - 详情页（`detail.ts`）：**阅读按钮要打开的那一话**（有进度就是上次那话，否则第一话）交给 `prefetch_chapter`。
  - 阅读器（`reader.ts`）：页码一变就看 `(currentIndex + 1) / images.length >= prefetch.next_at`，够了就给下一话排队（同一话只触发一次；**没有下一话就不触发**）。
- 改的文件：`backend/api.py`、`backend/config.py`、`config.yaml`、`frontend/src/prefetch.ts`（新）、`frontend/src/settings.ts`、`frontend/src/pages/settings.ts`、`frontend/src/pywebview.d.ts`、`frontend/src/pages/board.ts`、`frontend/src/pages/search.ts`、`frontend/src/pages/detail.ts`、`frontend/src/pages/reader.ts`、`README.md`。

## 预加载 验证记录（2026-10-14）

后端（临时库 + 临时缓存目录，跑完删；真图源真下载，album `123456` 第一话 84 张图）：

- `prefetch_albums(["123456"])` 返回 1、耗时 **0.3 ms**（不阻塞）；重复调用返回 0（记账生效）；`album:v2:123456` 随后真的落进缓存。
- `prefetch_chapter` 跑完磁盘上**正好 3 张**（`00001/2/3.webp`）；再叫一次返回 0（跳过）；删掉其中一张再叫返回 3（重新排队）。
- 预加载批次在跑的时候 `get_chapter` 要整话：最终 **84/84 全下完** —— `_dl_pending` 的补偿生效，没被预加载顶掉。
- `save_settings({'prefetch': {...}})` 三个键都能存；`next_at` 越界抛 `RuntimeError`；`albums` / `chapter_images` 设 0 后两个接口都返回 0。
- 踩的坑：预加载这条路不走 `get_chapter`，**目录得自己建** —— jmcomic 碰上不存在的目录是"静默不落盘"（请求照发、异常照吞、磁盘空）。第一轮就是这么挂的：日志里 `chapter_view_template` 都请求了，`images/` 里一张没有。

前端（无头 Chrome + 假 `window.pywebview` 桥：12 张假图、两个假本子，一个两话一个一话）：

- 首页 / 分类页：铺完 hero 与横条后 `prefetch_albums` 收到这些 ID；搜索页出结果后收到这一页 8 个 ID。
- 进 `#/album?id=a1`：`prefetch_chapter("p1")` —— 第一话，正是阅读按钮要打开的那一话。
- 阅读器翻到第 6/12 页（50%）**不触发**；按 `End` 到 100% 触发一次 `prefetch_chapter("p2")`；只有一话的本子按 `End` **不触发**。
- `tsc --noEmit` 与 `npm run build` exit 0（CSS 29.42 kB / JS 86.38 kB，比上一轮 +1.40 kB）。
- 没验的：真窗口里的实际体感（第一次进阅读器是不是明显快、看过的章节有没有重复下载）—— 交给用户。

## 搜索记录（最近搜索）改动清单（2026-10-14）

用户点名要的：搜索页记住搜过的词 —— 能点回去，也能删掉。

- 存储：纯前端 localStorage，复用 `store.ts` 的 `loadState` / `saveState`，键 `guzhu:search:recent`，上限 12 条；不动 `config.yaml`、不动 `data/app.db`、不加配置项、不要改 `pywebview.d.ts`（纯前端）。
- 记录时机：`doSearch()` 里过了"关键词非空 + 桥就绪"两道校验就记（真把请求发出去了才算搜过）；同一个词**无视大小写去重并挪到最前**（`rememberRecent()`）。
- 读的时候也清洗一遍（`loadRecent()`）：非数组 / 非字符串 / 空白 / 重复一律丢掉 —— 老数据、人手改过的 localStorage 都别想搞坏页面。
- 版式：`.search-filters` 和结果列表之间一块 `.search-recent`：左上「最近搜索」、右上「清空」，下面一行 chips（关键词 + ✕）；记录为空整块 `hidden`。
- 交互：点关键词 → 填进输入框 + 立刻重搜（用的是**当前**范围 / 排序）；✕ 删单条；「清空」清光并把焦点还给输入框。
- 空状态提示按"有没有记录"换一句：有记录才说"或者点上面的最近搜索"。
- 改的文件：`frontend/src/pages/search.ts`（记录读写 + chips 绘制 + 空状态文案）、`frontend/src/style.css`（`.search-recent` / `.recent-*`）、`README.md` 特性表「搜索」那条。

## 搜索记录 验证记录（2026-10-14）

- `tsc --noEmit` 与 `npm run build` exit 0（CSS 29.42 kB / JS 84.98 kB，比上一轮 +1.00 kB / +1.53 kB）。
- 行为（无头 Chrome + 假 `window.pywebview` 桥；先注入 `guzhu:search:recent = ['中文','同人','hanman','中文']`，探针把结果写进 DOM 再 `--dump-dom` 抓回来）：
  - 进页面：chips = `中文 | 同人 | hanman`（重复的「中文」在读取时就被丢掉），空状态提示确实是"…或者点上面的最近搜索"。
  - 点 ✕（首条）：chips 变 `同人 | hanman`，localStorage 同步成 `["同人","hanman"]`，整块没有被藏起来。
  - 点「清空」：chips 全没，`hidden=true`，localStorage 是 `[]`。
  - 点关键词：输入框被填成「中文」并发起搜索，8 张卡片铺出来、chips 仍在上面（截图核对版式：chips 一行、和筛选行的间距、✕ 的位置都正常）。
- 没验的：真窗口（WebView2）里的手感、真图源结果下的观感 —— 交给用户（5173 dev server 起来直接试）。

## 首屏「加载不出来」+ 论坛「空的」修复（2026-10-14）

用户报的：论坛点进去是空的；首页一般是**第一次进去加载不出来**，切到别的页再切回来才正常。

查出来三个原因（前两个是真凶，第三个是同类隐患）：

1. **建客户端要连图源，把开窗这件事也一起挡住了**（早先实测 10~27s）。`API.__init__` 里 `JmOption.default().new_jm_client()` 会更新域名 + 拉 `/setting`，这一步在 `create_window` 之前，窗口出不来的那十几秒里页面当然是空的。
   → `client` 改成**懒加载属性**（首次真要数据才建），并在 `__init__` 末尾起一个 `_warm_client` 后台线程**预热**：窗口立刻能出来，客户端在后台并行连上。
2. **虚化入场靠 `IntersectionObserver` 回调，窗口没在画就不回调**。`.board-panel .reveal album-card` 是 `opacity: 0; filter: blur(10px)`，全靠区块拿到 `.in` 才亮；窗口刚起来还没画第一帧、或整个被别的窗口盖住时 IO 不回调，首页就停在模糊态——看着就是"页面没加载出来"，切页回来重算一次才好。
   → `armReveal()` 挂完 observer 再用 `setTimeout` 在 400ms / 1500ms 各**自己量一次**（新增 `revealSoon()`：这一刻在视口里就直接加 `.in`，在屏幕外还是交给观察器按滚动演）。
   （补充实测：隐藏窗口里 CSS 过渡时钟是停的，`.in` 加上去算出来的 `opacity` 也还是 0；窗口一 `show()` 过渡就接着走完 —— 这条记在交接文档 §5.8。）
3. **首屏一律"要么全好、要么整页塌"**：hero 那一次请求失败（图源冷启动爱抖）之前会让**整页**进 `error`，下面各分类一个都不铺；桥慢半拍时 `load()` 也只有一句"还没就绪"、永不重来。
   → hero 失败不再连累下面（hero 位置上给一句 + 重试，横条照铺）；每条分类失败自动补一次（`row.retried`）；整页 / hero 失败自动重试 2 次（1.2s、2.4s 后再查，好了就撤）；新增 `waitForApi()` 盯着桥，桥一就绪自己重来；窗口回到前台（`focus` / `visibilitychange`）时：还没亮的横条补亮、页面要是还挂在错误上就自己重来一次——等于把用户"切页再回来"手动操作自动化了。
4. 论坛页等图源时铺**评论骨架**（`renderCommentSkeleton`，首屏 5 条 / 翻页 3 条），首屏失败自动重试 2 次并在底下提示"正在重试（第 N 次）"，翻页失败只提示一行、已铺出来的不动。

改的文件：`backend/api.py`（`client` 懒加载 + `_warm_client`）、`frontend/src/webstatus.ts`（新增 `waitForApi`）、`frontend/src/pages/board.ts`、`frontend/src/pages/forum.ts`、`frontend/src/components/states.ts`（`renderCommentSkeleton`）、`frontend/src/style.css`（`.hero-error` / `.comment-skeleton`）。

## 首屏修复 验证记录（2026-10-14）

全部是真 pywebview 窗口 + 真后端（临时探针脚本，跑完已删）：

- 真后端冷启动跑首页：T+1s 还空着（等桥 + 配置），T+2s `hero:3 rows:20`、卡片 `opacity:1`；日志里能看到 `_warm_client` 线程在开窗那会儿就连上图源了。
- 隐藏窗口（`hidden=True`，复现"窗口没在画"）：T+9s 兜底已经把 2/5 个区块量亮（`sec_in:2`），窗口 `show()` 之后卡片 `opacity 0 → 1`；同一条件下论坛也能铺出 10 条评论。
- 每个分类第一次请求必失败：T+1.0s hero 位置显示"最火的三部没拉下来"，T+2.0s 就被自动重试补上了（`hero:3 rows:20`）；后端调用时间线：六个分类第一次全失败 → 1.2s 后第二次全部成功。
- 图源"整挂"（`get_ranking` 一律抛）：首页停在 hero 报错 + 各段自己的重试按钮，**不塌成整页空白**；放开图源 + 派一个 `focus` 事件 → 自己恢复成 `hero:3 rows:20`。
- 桥"迟到"（临时摘掉 `window.pywebview.api` 再进首页）：先显示"还没就绪"，桥一装回去自己重来，出到 `hero:3 rows:20`。
- 论坛 `get_forum` 慢 6 秒：T+2s 铺着 5 个骨架块，数据到了换成 10 条评论。
- `tsc --noEmit` / `npm run build`（CSS 28.42 kB / JS 83.45 kB）/ `py_compile backend/api.py` 全 exit 0。
- 没验的：用户自己开的那个真窗口里的观感——交给用户。

## 热门榜单改版 改动清单（2026-10-13）

版式（用户口径，2026-10-13 二次澄清后定的）：hero 还是最火的三部；hero 下面是一条**分类标签条**（原来的 chips，用户嘴里的"导航栏"），当前分类那个标签**和下面的面板同色、接成一块**（标签 + 标签的内容）；首页那一页的面板里按分类铺横条，一个分类一行、行左边分类名右边「更多」；点标签或者「更多」进对应分类的界面，那个界面同样有标签条和 hero，但 hero 是该分类的前三部；**首页面板里没有「全部」这一段**（全部就是这一页本身）。左侧导航保持原样，不动。

- 新增 `pages/board.ts`：首页和分类页**共用**这一套（hero + 标签条 + 面板），`boardPage(category)` 一个入口；`pages/popular.ts` / `pages/category.ts` 变成两行包装（`boardPage('all')` / `boardPage(pickKey(params.c, …))`）。
- hero：`get_ranking(range, 当前分类, 1, sort)` 的前三部——首页就是全部最火三部（跟改版前一样），分类页就是该分类最火三部。
- 首页面板：除「全部」外的每个分类一段（`.cat-section` = `.cat-head` 分类名 + 「更多 ›」 + `.cat-row` 一行），各自发一次 `get_ranking`，谁先回来谁先铺，互不阻塞；某类这期没作品就整段藏起来；单段失败只在那一段里给「重试」。
- 分类页面板：该分类的整页网格，前三部已经在 hero 里所以从第 4 部开始铺，往下用「加载更多」翻页（图源不给总数，就用"这一页空了"当到底）。
- 一行几张：`colsFor()` 按面板内宽算（卡片按 148px + 16px 间距估），写成 CSS 变量 `--cols`；`ResizeObserver` 盯着面板宽度，一变就重算并重铺。窗口默认宽度下面板内宽 ~886px → 一行 5 张。
- 虚化入场：`IntersectionObserver` 盯的是**区块**（首页每个 `.cat-section`、分类页整页网格 `.album-list.reveal`），区块进视口那一下给它加 `.in`（加完就 `unobserve`，只演一次），里面卡片按 `--i` 每张错开 55ms（`transition-delay: calc(var(--i,0)*55ms)`）；`prefers-reduced-motion` 下不走 observer，直接加 `.in` 到位。
  挂载时机：首页是**等这一段的真卡片铺好之后**才挂（`row.armed` 防重复），否则骨架阶段就进过视口、真卡片铺出来反而不演；`load()` 里每次换榜单都清掉 `.in` 与 `armed` 重来。CSS 规则是 `.board-panel .reveal album-card`（暗）→ `.board-panel .reveal.in album-card`（亮），**不挂在面板上**。
- `style.css`：`.board` / `.board-head`（标签条 + 右侧榜单·排序）/ `.board-tab(.active)`（当前标签 `margin-bottom: -1px` + 底边用面板色盖住面板上边线，接缝就没了）/ `.board-panel`，加上原来那套 `.cat-*`、`.board-empty`、`.cat-back` / `.load-more` / `.load-hint`。
- 这次**没有**动 `#app` / `#nav` 的布局，也没有 `body[data-page]` 之类的路由挂钩（上一版误把"导航栏"当成左侧侧栏，做了一套把导航和面板接成一块的规则，已全部撤掉）。

## B4 改动清单（2026-10-13）

后端（`backend/api.py`）

- `_init_db()` 在 `DATA_DB`（`~/.jmreader/data/app.db`）建表 `favorite(album_id TEXT PRIMARY KEY, title, cover_url, added_at REAL)`。放 `data/` 而不是 `cache/`：收藏是再生不出来的用户数据，清缓存 / 定时清理都不动它。
- 新增 4 个 js_api：`is_favorite(album_id)` → bool、`toggle_favorite(album_id, title='', cover_url='')` → 切换后的 bool、`remove_favorite(album_id)` → None（没收藏过也不报错）、`get_favorites(limit=100, offset=0)` → `[{album_id,title,cover_url,added_at}]`（按 `added_at` 倒序）。
- 入参校验抽出 `_need_album_id()`：空串 / 纯空格 / `None` 一律 `ValueError("缺少漫画 ID")`（`str(None)` 会变成 `"None"`，所以 `None` 得单独挡）。
- `get_favorites` 的 `limit` / `offset` 走 `_cfg_int` 容错（非法值回默认，不报错，和 `get_comments` 的 page 一致）。
- **没有新配置项**（收藏不需要），所以这次不涉及「加配置改 5 处」。

前端

- `types.ts`：新增 `FavoriteItem`；`pywebview.d.ts`：新增 `FavoriteItem` + 4 个方法声明。
- `components/icons.ts`：新增 `heart`(Heart) / `heartOn`(HeartPulse) / `trash`(Trash2) —— 图标仍然只从这一个出口出。
- `pages/detail.ts`：顶部从单个「返回」变成 `.detail-top` 一行（返回在左、心形在右、中间留给出错提示）；载入时 `Promise.all` 多问一次 `is_favorite`（失败当"没收藏"，不影响详情）；`paintFavorite()` 做**乐观更新 + 失败回滚**，以后端返回的 bool 为准，`busy` 防连点。
- `pages/favorites.ts`（新）：`#/favorites` 页，`get_favorites(200)` 铺卡片（`.fav-cell` 包 `<album-card>`），角上一个 `trash` 按钮取消收藏（`stopPropagation`，删完只改本地数组重画，不重拉全表）；空状态用 `renderEmpty` + 去热门；出错走页面顶部 `.fav-error`。
- `main.ts`：`NAV_ITEMS` 加「收藏」一项（`heart` / `heartOn` 变形）、注册 `#/favorites` 路由。
- `style.css`：新增 `.detail-top` / `.fav-hint` / `.fav-btn(.on)` 与 `.fav-cell` / `.fav-del` / `.fav-error`；已收藏态用暖色（`#ff6b81`），和阅读进度那个蓝色强调色区分开。

## 本轮（B1 + 章节折叠 + 配置项）改动清单（2026-10-13）

新增配置（按「加配置要动 5 个地方」的纪律，一处没漏）

- `backend/config.py · DEFAULT_CONFIG`：新增 `detail.chapters_collapse`（默认 20，0 = 不折叠）、`detail.comment_preview`（默认 5，0 = 不显示评论区）；`cache.comment_ttl`（默认 600）。
- `config.yaml`：同步写入当前值。
- `frontend/src/settings.ts`：`AppSettings.detail` + `DEFAULT_SETTINGS.detail` + `cache.comment_ttl`，并在 `loadSettings()` 里做逐层合并。
- `frontend/src/pages/settings.ts`：新增「详情页」分组（两行），「下载与缓存」组加 `cache.comment_ttl`。
- `backend/api.py · save_settings()`：放行 `detail.chapters_collapse`（0~500）、`detail.comment_preview`（0~50）、`cache.comment_ttl`（0~30 天）—— 没放行的会被静默忽略，这是老坑。

后端

- 新增 `get_comments(album_id, page=1)`：`album_pagination` 只读拉取，返回 `{total, has_more, items:[{nickname, content, created_at, spoiler, reply}]}`；缓存键 `comments:<id>:<page>`，时长走 `cache.comment_ttl`。**不需要登录**。
- `__init__` 读入 `self._comment_ttl`。

前端

- `frontend/src/types.ts`：新增 `CommentItem` / `CommentPage`。
- `frontend/src/pywebview.d.ts`：新增 `get_comments` 声明。
- `frontend/src/pages/detail.ts`：详情页改成两栏 —— 左栏是原来的内容（封面 / 热度 / 日期 / 相关作品 / 章节），右栏是评论区；章节超过阈值只铺前 N 话，另给「展开全部 N 话」和「跳到上次读到的第 N 话」；评论区首屏铺 `comment_preview` 条，点「看更多」先摊开本页再取下一页；剧透评论用 CSS 模糊盖住，点一下展开；回评带「回评」标签。
- `frontend/src/style.css`：新增 `.detail-layout`（窗口窄于 1040px 自动退回单栏并取消 sticky）、`.chapter-actions`、`.detail-side` / `.side-title` / `.comment*`。注意 `button[hidden]` 要显式 `display: none`（`button` 的 `display: inline-flex` 会盖掉 `[hidden]`）。

## 热门榜单改版 验证记录（2026-10-13）

- `tsc --noEmit` 与 `npm run build` exit 0（CSS 26.88 kB / JS 77.12 kB）。
- 真版式是**用无头 Chrome 截图看的**（本机没有可用的 Computer-Use 浏览器）：把 `frontend/dist` 拷到临时目录，插一段假 `window.pywebview` 桥（假数据、封面都指 `/apple-touch-icon.png`），`python -m http.server 5199` 起在临时目录，`chrome --headless=new --screenshot` 出图。**5173 没占**，跑完临时目录 / 截图 / profile 全部删掉，5199 的进程也停了。
- 看的结果：首页 `#/popular` —— hero 三部照旧，下面标签条「全部(亮) 同人 单本 短篇 韩漫 美漫」+ 右侧「周榜 / 按观看」，当前标签和面板之间没有分隔线、同底色（接成一块）；面板里是同人 / 单本 / 短篇 / 韩漫 / 美漫 各一行，行头左边分类名、右边「更多 ›」，**没有「全部」这一段**；一行 5 张（面板内宽 ~886px）。
- 分类页 `#/category?c=hanman`：标题「韩漫」、hero 是该分类前三、标签条里「韩漫」是亮的并和面板接成一块、面板里是该分类的整页网格、左上角有返回、下面有「加载更多」。
- 虚化入场：无头 Chrome 抓不到终态（它不推进 CSS transition，截到的永远是动画开头那一帧），所以**又加跑了一遍 `--force-prefers-reduced-motion`**——那条路径下 JS 直接给区块加 `.in`，看到的就是入场结束后的样子：首页每个分类段 5 张卡片齐全、接缝正常；分类页从第 4 部起铺满、底下「加载更多」。**真窗口的虚化手感还是留给用户确认**。
- 没验的：真窗口（WebView2）里的毛玻璃模式、窗口拖宽时列数实时变化的手感、评论 / 详情页等其他页面（这次没动）。

## B4 验证记录（2026-10-13）

- 测法：把 `backend.api.DATA_DB` 指到临时库再 `API()`，**不往真实收藏里塞测试数据**，跑完删临时库。
- 加 / 查 / 取消 / 重复取消：`toggle_favorite` 回 `True`→`is_favorite` True→再 toggle 回 `False`→`remove_favorite` 幂等不报错。
- 列表：字段就是 `album_id/title/cover_url/added_at` 四个；`limit=2` 与 `offset=1` 分页正确；按 `added_at` 倒序。
- 容错：`limit='abc', offset='xyz'` 回默认不报错；`title='  空格  '` 存进去是 `'空格'`。
- 校验：`is_favorite('')` / `is_favorite('   ')` / `toggle_favorite('')` / `remove_favorite(None)` 全抛 `ValueError(缺少漫画 ID)`。
- 建表：临时库里 `history` + `favorite` 两张表都在（老的库升级就是走 `CREATE TABLE IF NOT EXISTS`，不用迁移）。
- 前端：`tsc --noEmit` 与 `npm run build` exit 0（CSS 24.69 kB / JS 73.29 kB，比上一轮 +0.92 kB / +3.59 kB）。
- ⚠️ 没做：真窗口点一遍心形 / 收藏页删除 / 空状态 —— 需要用户的 5173 dev server。

## B1 + 章节折叠 验证记录（2026-10-13）

- `python -m py_compile backend/api.py`、`tsc --noEmit`、`npm run build` 全部 exit 0（CSS 23.77 kB / JS 69.70 kB）。
- `get_comments('287234')`：第 1 页 total=4434、10 条、`has_more=True`；第 2 页与第 1 页内容不同；重复调用 0.002s 命中缓存；`page='abc'` 抛 `ValueError`，`page=0/-3` 容错成第 1 页；缓存键 `comments:287234:1|2`。
- 评论字段：`nickname` / `content` / `created_at`（图源给的是 `Oct 13, 2026` 这种人类可读格式）/ `spoiler` / `reply`。
- **未做**：真窗口（`main.py`）人工看版式 —— 需要用户的 5173 dev server，建议重点看：两栏宽度、窄窗口退回单栏、章节折叠按钮、评论区"看更多"。

## A3 改动清单（2026-10-13）

- `backend/api.py · get_album_detail()` 新增 `comment_count`、`pub_date`、`update_date`、`related:[{id,title,author,cover_url}]`（同一个 `album` 对象，无额外请求）。
- 缓存键升为 `album:v2:<id>`；缓存里**不放封面地址**（图源域名会变、镜像随机），返回前现拼。
- `frontend/src/types.ts` 新增 `RelatedAlbum` 并扩充 `AlbumDetail`；`frontend/src/pages/detail.ts` 补热度行「💬 评论数」、日期行（`''`/`'0'` 不显示、与发布同天不重复）、简介下方的「相关作品」卡片（复用 `renderAlbumList`）。

## B2 改动清单（2026-10-13）

- 新增 `frontend/src/store.ts`：`loadState` / `saveState` / `pickKey`，前缀 `guzhu:`；读坏 / 隐私模式 / 存储被禁用一律回退默认值。
- `popular.ts` 记 `{range, category, sort}`；`search.ts` 记 `{scope, sort}`（URL 参数优先）。

## A1 / A2 改动清单（2026-10-13）

- 后端新增 `_SCOPE_MAP` / `_ORDER_BY_MAP`，`search()` 加 `scope` / `order_by`，`get_ranking()` 加 `order_by`（非法值抛 `ValueError`，缓存键带上新维度）。
- 前端新增 `frontend/src/components/picker.ts`（榜单 / 排序 / 搜索范围共用的下拉），`search.ts` / `popular.ts` / `pywebview.d.ts` / `style.css` 同步。

## B5 论坛页 改动清单（2026-10-13）

- 后端 `backend/api.py` 新增两个 js_api：
  - `get_forum(page=1)` → `{total, has_more, items:[{comment_id, nickname, content, created_at, spoiler, reply, reply_count, album_id, cover_url}]}`。走 `client.forum_pagination()`（API 客户端打 `/forum?mode=all&page=`，**只读、不用登录**）；缓存 `forum:<page>`、时长复用 `cache.comment_ttl`；**封面地址现拼不进缓存**（`_with_covers()` 是把缓存那套外挂一层，跟 `get_album_detail` 一个路子）；`has_more` 满一页且没到 `page_count` 才算 true（服务端封顶 5000 条 / 500 页）。
  - `get_album_titles(album_ids)` → `{id: 标题}`。最多 30 个、并发 5，内部直接走 `get_album_detail`（**复用详情缓存，等于顺手预热**）；单个失败就跳过那个 ID，不抛。
  - 没有新配置项；`likes` 实测 50 条全是 0（移动端接口不给），所以没进契约。
- 前端：新增 `pages/forum.ts`（留言卡直接复用详情页评论区那套 `.comment*` 样式；「加载更多」复用 `.comment-more`）、`icons.ts` 加 `forum` / `forumOn`（`MessagesSquare` / `MessageSquareText`）、`main.ts` 加路由 `/forum` 与侧栏导航项「论坛」（排在「搜索」后面）、`types.ts` 加 `ForumComment` / `ForumPage`、`pywebview.d.ts` 加两个方法、`style.css` 加 `.forum-*` 一小段。
- 交互细节：封面条先显示 `JM<id>`，`get_album_titles` 回来再换成真标题（失败就一直是 ID）；剧透的点击监听挂在**文字**上而不是整张卡（卡里有个封面按钮，免得一点就顺手摊开）；首屏失败给整页重试，翻页失败只在底下提示一行、已铺出来的不动；切走后晚回来的请求被 `alive` 丢掉。

## 卡片悬浮手感（2026-10-13）

- 用户点名：鼠标悬浮时卡片再大一点、加阴影。`album-card:hover` 从 `translateY(-3px)` 改成 `translateY(-4px) scale(1.06)`，背景由 `--surface-2` 提到 `--surface-3`，投影用新 token `--shadow-card`（`0 18px 42px rgba(0,0,0,.8), 0 5px 14px rgba(0,0,0,.55)`）。
- 卡片本体加 `position: relative`、悬浮时 `z-index: 2`，放大后盖住旁边卡片而不是被后一张压住；`transition` 补上 `box-shadow .18s`（榜单入场那条过渡也一起补，否则投影会"啪"地跳出来）。
- 验证：`npm run build` exit 0（CSS 27.03 kB / JS 77.12 kB）；无头截图核对过悬浮态（把构建产物里 `album-card:hover` 那段声明原文抠出来挂到固定卡片上截的，保证和真 hover 一致）。

## B5 验证记录（2026-10-13）

- `py_compile backend/api.py` / `tsc --noEmit` / `npm run build` 全 exit 0（CSS 27.84 kB / JS 81.11 kB，比上一轮 +0.81 kB / +3.99 kB）。
- 后端（临时库跑，跑完删，不碰真缓存）：`get_forum(1)` → total 5000 / 10 条 / `has_more=True`；字段与设计一致；`album_id` 为空串那条 `cover_url` 也是空串，其余能拼出 `.../media/albums/<aid>.jpg`；第 1 页第二次调用 0.002s（命中缓存）；`get_forum(2)` 内容与第 1 页不同。
- `get_album_titles`：8 个 ID 并发拉 2.28s、第二次走详情缓存 0.01s；重复 ID / 空串被去重；坏 ID（`999999999999`）返回 `{}` 不抛。容错：`get_forum('abc')` 抛 `ValueError("评论页码要是数字")`，`get_forum(0)` 当第 1 页；`get_album_titles('x')` 抛 `ValueError`。
- 端到端（无头 Chrome + 真后端）：把 `frontend/dist` 拷到临时目录，页面里插一段 pywebview 桩走 HTTP 打到**真的 API 实例**上（临时目录的库和缓存），截图确认首页评论、封面、标题都对。后端调用日志证明整条链子通：
  `get_settings` → `get_forum [1]` → `get_album_titles`（10 个 ID）→ 点「加载更多」→ `get_forum [2]` → `get_album_titles`（7 个 ID，另外 3 条没挂本子）→ 再点 → `get_forum [3]`。
- 分支渲染用假数据截图核对过：没挂本子 → 不出现封面条；回评 / 「N 回复」两个小标签；剧透 → 文字糊住；拿不到封面 → 封面条只剩标题；`has_more=false` → 按钮藏起来、底下显示「到底了 —— 服务端只留最新的 5000 条评论」。
- 没验的：真窗口（WebView2）里滚动手感、缩略图懒加载的实际观感 —— 交给用户。

## 决策记录

- **2026-10-13**：文档按用户要求放 `tmp/`，不建 `docs/` 与根 `STATUS.md`。
- **2026-10-13**：一切需要登录 / 落盘账号凭据的能力都不做（隐私风险）；收藏改做本地版（B4）。
- **2026-10-13**：详情页的行为（折叠阈值、评论条数）都进 `config.yaml`，不留硬编码；新增配置严格按 5 处同步。
- **2026-10-13**：收藏态别塞进 `album:<id>` 详情缓存（24h TTL），要单独查本地表（B4 已按这条做：`is_favorite` 每次进详情现查）。
- **2026-10-13**：收藏表放 `data/`（用户数据），不放 `cache/`；收藏行里的 `title` / `cover_url` 是加收藏那一刻的快照，图源换线路后封面可能失效 —— 换回线上的实时地址要每次请求详情，不划算，先接受这个代价。
- **2026-10-13**：心形做"乐观更新 + 失败回滚"，`toggle_favorite` 返回切换后的状态，前端以它为准（不靠本地猜）。
- **2026-10-13**：用户说的「中间的导航栏」= hero 下面那条**分类标签条**（原来的 chips），不是左侧侧栏；「标签和内容连起来」指的是**当前分类标签和下面的面板**接成一块。上一版把左侧侧栏当标签做的合并规则已全部撤掉，左侧导航保持原样。
- **2026-10-13**：首页（`#/popular`）面板里不铺「全部」这一段——它想「看全部」就点标签条上的全部，那是同一页；分类页（`#/category?c=`）则铺该分类自己的整页列表。所以「更多」进分类页是"看这个分类的全部"，首页则是"别的分类各一行"的导航页。
- **2026-10-13**：hero 属于"当前这一页的分类"：首页是全部前三（跟改版前完全一致），分类页是该分类前三；分类页的列表因此从第 4 部开始铺，不跟 hero 重复。
- **2026-10-13**：榜单（日 / 周 / 月）和排序仍然只有一套（localStorage 里那份），两个页面共用；改了就两页都变。
- **2026-10-13**：一个分类一行只铺 `--cols` 张（按面板内宽算，卡片按 148px 估），多出来的靠「更多」进分类页；分类页的「加载更多」以"这一页空了"当到底（图源不给总数，不猜）。
- **2026-10-13**：详情缓存里不放绝对封面地址（交接文档 §5.7）；代价是浏览器 HTTP 缓存命中率下降。
- **2026-10-13**：排序对外只暴露语义名，jmcomic 短码不外泄。
- **2026-10-13**：页面上的临时选择走 localStorage，不进 `config.yaml`。
- **2026-10-13**：确认「只看汉化」不能靠 `sub_category` 直接接（`JmApiClient` 静默忽略），需引入 `impl='html'` 第二客户端。
- **2026-10-13**：`get_meta_data()` 返回 HTTP 客户端元数据，不是图源版本；要版本号用 `JmModuleConfig.APP_VERSION`。

- **2026-10-14**：开窗不再等图源：`client` 懒加载 + `_warm_client` 后台预热（窗口立刻出来，第一次请求不用干等十几秒）。
- **2026-10-14**：虚化入场不能只靠 `IntersectionObserver`（窗口没在画就不回调），必须配"过一会儿自己量一次"的兜底；首屏任何一处失败都不能把整页带走，一律降级成局部提示 + 自动重试。
- **2026-10-14**：搜索记录属于**界面记忆**不是用户数据，做在 localStorage（`guzhu:search:recent`，12 条），不建 `data/app.db` 的表：丢了不影响阅读，跟 B2 的范围 / 排序一个路子。
- **2026-10-14**：搜索记录只存关键词，不存范围 / 排序 —— 点 chip 按**当前**筛选条件重搜；存了就会让"同一个词换范围"变成两条记录。
- **2026-10-14**：搜索记录常显（出了结果也留在上面），不做"聚焦才弹"的下拉：搜索页本来就空着，一行 chips 少一层交互。
- **2026-10-14**：A4「只看汉化」按用户意见**暂缓**，本轮先做搜索记录。
- **2026-10-14**：开场字标**落位定稿** —— 字标只取代品牌行里的「孤竹」两字（品牌行 = `GuZhu漫画`），
  不是取代整行；落点是新加的 `.brand-slot`，导航里字标 88 → **76px**（208px 的 rail 塞不下 88px + 两个字，一折行「漫画」就变竖排）。
- **2026-10-14**：**阅读器浮层不做毛玻璃**（用户定：漫画的内容不要做毛玻璃特效）。口径是「毛玻璃只给壳、不压在漫画图上」；
  五处浮层删掉 `backdrop-filter` 并把底色填实（.88~.94），撤了模糊不填色的话字会糊在纸页上。
- **2026-10-14**：详情页左栏顺序定为 **章节在前、相关作品在后**（用户定）—— 章节是「要读的东西」，比推荐位要紧。
  实现只是模板里换 DOM 顺序，`related` 的取数与章节折叠逻辑都没动。
- **2026-10-14**：搜索页的关键词**进地址栏**（`#/search?q=…`，`replaceState`）：页面状态不能只活在局部变量里，
  否则 `history.back()` 回来的是个空页（用户报成"返回回到首页"）。用 replace 是"换词不堆历史 + 返回正好落在带词那条"两头都要；
  按地址栏还原那条路**不记 `search_log`**（次数是推荐画像的输入，不能被返回键刷高）。
- **2026-10-14**：A4「只看汉化」由「暂缓」改为**不做**（上一条作废）。`related_list` 那条不算待办 ——
  详情页「相关作品」早在 A3 那轮就吃了 `album.related_list`（`get_album_detail` 的 `related` 字段），
  推荐二期只是再拿它当「图上的邻居」。
- **2026-10-14**：预加载一律"立刻返回 + 后台线程"：桥上的调用排在用户点击前面，预热这种慢活不能占着它。
- **2026-10-14**：条数 / 张数上限放后端（`prefetch.albums` / `chapter_images`，重启生效），只有"看到几成就预加载下一话"放前端读 —— 滚动的事只有前端知道。
- **2026-10-14**：详情页预热的是"阅读按钮要打开的那一话"（有进度就是上次那话），不是死板的第 1 话：用户原话是"第一章"，但按阅读路径取才有用（要看严格的第一话，改 `detail.ts` 一行）。
- **2026-10-14**：首页只预热"这一刻真铺出来的"（hero + 各行前 `--cols` 张），不把图源给的一整页都拉一遍。
- **2026-10-14**：预加载批次不许顶掉"整话下载"（`_dl_pending` 补偿）—— 不这么做，用户进阅读器那次请求会被吃掉，缺的图永远下不来。

- **2026-10-14**：搜索记录**搬进 `data/app.db`**（原来是 localStorage）：推荐的搜索信号要"次数 + 时间"，只有后端算得了；chips 与画像共用同一份真相。
- **2026-10-14**：搜索页的推荐**不吃本次关键词**（用户原话「不吃」）—— 一期与首页完全一致；`get_recommendations` 的 `kind` 留着给二期分叉。
- **2026-10-14**：候选池默认 **40**（不是 60）—— 它是**覆盖度**旋钮不是速度旋钮：榜单走缓存、tag 读本地缓存、没缓存的候选算 0 分，推荐段还是异步铺，所以不拖启动。
- **2026-10-14**：收藏态**不进缓存**，所有列表接口返回前现拼 —— 否则刚收藏完，列表里还是没角标（`album:v2:` 有 24h TTL）。
- **2026-10-14**：已收藏角标**只在真收藏时才有这个 DOM**（没收藏的不留空位、也不给灰标）；**收藏页不打**（整页都是收藏 + 卡片角上已有删除按钮），详情页保持心形。
- **2026-10-14**：`cold = 画像空 或 候选一个都没命中`，那时标题写「热门推荐」而不是「为你推荐」—— 没命中还说"为你推荐"是骗人。
- **2026-10-14**：推荐失败 / 拉得慢 / 配置里关掉，**整段藏起来**，连 console 都不吵：它在首页最显眼的位置，但不能连累 hero 与分类横条。
- **2026-10-14**：收藏时存 tag / 作者**快照**（详情页传过来），不靠详情缓存（24h 就过期，一周后画像空一半）。
- **2026-10-14**：作者维度一期就做（用户点名），`author_boost = 1.5`：作者是很准的信号，命中就该明显加分。
- **2026-10-14**：隐式反馈（点开详情那档）**砍掉**，一期只用收藏 + 搜索。

- **2026-10-14**：**「下载进度」就是磁盘上落地的文件**，进程里不留计数 —— 续传时重算缺哪些（`_pending_chapters`
  顺带量一次目录）。这样关窗 / 断电 / 图源抖都只补缺的，不用维护一份可能跟磁盘对不上的计数。
- **2026-10-14**：离线副本放 `download.dir`（用户数据），**不进 `cache/`** —— 进去就会被「整理缓存」删掉。
- **2026-10-14**：`download_chapter` 主键用 `(album_id, photo_id)`（照 `history` 的规矩）：photo_id 全站唯一只是
  图源的约定，不该拿来当本地表的主键（测试里两本撞 ID 时，第二本的话被静默吃掉）。
- **2026-10-14**：图片服务改成**能挂多个根**（`/images` → cache、`/downloads` → `download.dir`）：离线副本在 cache
  之外，阅读器要读到它只能这么接；顺带 `get_chapter` 命中离线副本时**不再往 cache 里下第二遍**。
- **2026-10-14**：一话下不下来**不阻塞整本**（只标那一话 error），单张图重试 `download.retries` 次；
  这是"断线重连"的粒度选择：网络抖一下不该让整本从头再来。
- **2026-10-14**：任务状态里 `running` 也算"没下完" —— 上次被关窗打死就是停在 `running` 上，开窗自动接上。
- **2026-10-14**：详情页「下载」跟「阅读」**同一排**（用户点名），标签跟着任务状态走；只有详情页开着且任务在跑时
  才轮询，路由一切走就停表。
- **2026-10-14**：下载页的按钮放**卡片下面**，不压封面角 —— 148px 的卡片角上塞两个按钮会跟进度角标挤成一团
  （截图才看出来）。
- **2026-10-14**：详情页标题 / 作者 / 观看收藏数 / 标签的实色底**写死颜色**，不用 `--bg` 变量：毛玻璃开着时
  那套变量是半透明的，拿它垫等于没垫。

- **2026-10-14**：首页 hero 与下面的推荐段 / 分类横条**去重**（用户要求）：在**取回来的整页里**剔、再切前 `--cols` 张（切完再剔会把横条削短）；去重名单由 `board.ts` 持有（`heroIds`），推荐段通过 `shownAbove()` 拿 —— 所以**推荐段的 `load()` 必须等 hero 落定才调**（早调拿到的是空名单，等于没去重）。
- **2026-10-14**：判断 pywebview「又注入了一遍」**别只听 `pywebviewready`**，看**方法引用变没变**（`_createApi()` 每次都 `new Function()`）：事件有可能在我们的监听挂上之前就派发完了（桥比脚本先就绪），那种情况下"最近一次注入"无从得知，闸门会当场放行。`waitForBridge` 的 `quietMs` 取 **800ms**（实测两遍最多差 ~400ms）；等它的代价是 0 —— 闪屏要等首页铺完（`splashReady`）才揭幕。
- **2026-10-14**：真窗口验证**用真的 pywebview**（`tmp/_probe_bridge.py`，三路仪器打时间线），别只信无头 Chrome 里的假桥 —— 这个 bug 恰恰只在真桥「注两遍」的时序里现形。
- **2026-10-14**：开场动画**写死在 `index.html` 里**（内联 HTML + CSS + SVG），不放 `main.ts`：它是唯一“早于应用 JS”的位置，dev 态模块图那几百 ms 里就已经在画了。
- **2026-10-14**：闪屏**不阻塞路由**——首页在闪屏底下照常铺，揭幕时露出的是成品；骨架→内容那段过程用户完全看不见，也避免 hero 的虚化入场在揭幕后重演。
- **2026-10-14**：字标用**手画单线 SVG path + `stroke-dashoffset` 描边**，不用普通字体转 path（转出来是轮廓，含孔字母会“先描外圈再描内圈”）；打字体的备选只当 `splash.style: font` 的降级开关。
- **2026-10-14**：落位用 **FLIP**，不用 View Transitions：MDN 写明调用期间文档 `hidden` 会整个跳过，而 pywebview 启动期恰好可能不可见。
- **2026-10-14**：预热只有一条原则——**复用首页那一批 cache key**，让首页后面那次请求命中缓存；实测暖缓存下首页 6 个分类元数据 9~11ms，冷启动 ~2.2s，动画遮的就是这 2 秒。
- **2026-10-14**：开场动画实测（假图源，单次 0.4s）：`prefetch_home` 7 个任务并发跑完 → 首页自己那 6 个分类 **512ms** 拿齐（不预热 2.4s；`max_workers=4` 的版本排两批，比不预热还慢）；再拉一次 **9ms** 全命中；图源侧 6 个分类各 1 次 + 推荐候选池 `page=2` 1 次 = 共 7 次，没重复拉；同一把 key 6 个线程同时来，图源只被调 1 次。无头 Chrome：揭幕 2520ms（首页铺完才揭）、`splash.enabled:false` 331ms、reduced-motion 1420ms（跳过描字）。
- **2026-10-14**：动画时长 = 描字 ~1.1s + 收尾 ~0.5s，最短 1.1s / 最长 2.4s，**可点一下 / Esc 跳过**；`prefers-reduced-motion` 直接跳过描字与飞入。
- **2026-10-14**：`main.py` 要显式传 `background_color="#07080a"`（pywebview 默认白，窗口在导航开始时就 show，“闪白”发生在我们的 HTML 之前）；但毛玻璃开着时（`transparent=True`）这个参数会被 pywebview 忽略，那条路先真机看。
- **2026-10-14**：字标返工（真机看过之后）—— 笔画 14→25、字身放大（viewBox `0 0 590 240` → `23 45 637 161`，闪屏 `min(46vw,460px)`→`min(56vw,620px)`，导航 70→88px）、`u` 的碗宽从 x 高的 0.48 修到 0.65（跟 `h` 的肩膀同宽）。「边缘碎片化」查明是两处几何没对齐：`u` 的碗底那两段 `Q` 不切（看着有折角），`h` 的肩膀起点比竖线中心偏左 3 个单位（圆头探出个疙瘩）；现在 `u` 用半圆的三次贝塞尔、`h` 的肩膀终点落在竖线中心线上。闪屏加了一层 `backdrop-filter: blur(24px)` 深色毛玻璃，字标改成白→灰蓝渐变描边 + 写完淡入一层辉光。
- **2026-10-14**：字标改**斜体**（绕基线斜切 14°，直接算进路径坐标，不吃系统字体）+ **描字放慢**（1000→1500ms，停留 300→450ms，`min_ms` 1300→1950 / `max_ms` 2400→3000 三处同步）。斜切对 `A` 弧不成立（会变成椭圆弧），所以先把 G 的 250° 弧和 h 的肩膀换成三次贝塞尔再切 —— 路径里现在没有 `A` 了。手写体那条路（`Segoe Script` / `Ink Free` 这类 Windows 自带字体）也当场验过能出效果，但得放弃逐笔描字、改成 mask 扫过，且字宽受字体影响 —— 先不做。
- **2026-10-14**：「我的下载」空态修好了 —— 没下过任何东西的人一进页面看到 4 张骨架卡片一直闪。原因是 `downloads.ts` 的 `renderedIds` 起手写成 `''`，跟空列表算出来的 `''` 撞上，`sync()` 一直以为已经画过了，空态永远铺不出来。起手改 `null`。

- **2026-10-14**：打包用 **PyInstaller `--onedir`**，不用 `--onefile`（onefile 每次启动解压到 `%TEMP%`，是杀软误报的头号来源）；分发成 zip，解压双击即用。
- **2026-10-14**：发布态**不走 `file://`**，由进程内的本地 HTTP 服务挂 `frontend/dist`（file:// 下 ES module 会被 CORS 拦、localStorage 也不是稳定 origin）。Vite 侧不用改（不需要 `base: './'`）。
- **2026-10-14**：静态服务端口**固定 47753**（< 49152 避开 Windows 动态端口段，> 4096 免管理员；实测空闲），被占则 47754…47760 依次退让；**固定端口的目的是保 origin 稳定**，否则 `localStorage`（主题 / 榜单偏好）每次开窗都像被重置。
- **2026-10-14**：图片服务与静态服务**合并成一个端口**（方案 A）：图片与页面同源，WebView2 的图片缓存跨次有效，只监听一个口。`API.__init__` 因此要接受外部传入的 `base_url`。
- **2026-10-14**：`webview.start(private_mode=False, storage_path=~/.jmreader/webview)` —— pywebview 默认 `private_mode=True` 会把 WebView2 user data 丢进临时目录，主题与偏好每次开窗清空。
- **2026-10-14**：配置落用户目录：开发态继续读仓库根 `config.yaml`（保持手感），冻结态读 `~/.jmreader/config.yaml`（首启用默认值写一份）；统一入口放 `backend/paths.py`。
- **2026-10-14**：`.ps1` 一律存 **UTF-8 带 BOM**（PS 5.1 把无 BOM 脚本按 ANSI 读，中文注释会直接搞坏语法解析）—— 这是 `AGENTS.md` 里「脚本 UTF-8 无 BOM」的**例外**，那条针对 sh / `.py`。
- **2026-10-14**：发布形态用 `--windowed`（实测与 console 行为一致）；但 `evaluate_js` 在 windowed 冻结态会永久挂住，探针改用「页面自己通过真桥回报」（`tmp/_probe_exe.py`）。
- **2026-10-14**：**启动闸门必须等「方法挂上」**，不能只判 `window.pywebview?.api` 在不在 —— pywebview 是两步注入（`js/api.js` 先建**空对象** `{api:{}}`，判真；`js/finish.js` 才挂方法、再派发 `pywebviewready`）。`waitForPywebview()` 因此换成 `waitForBridge(method='get_settings')`（等具体方法 + 每 100ms 轮询 + 监听事件兜底；2026-10-14 又加了 `quietMs=800` 的静默窗与「按方法引用变化判重注入」，见上面那份改动清单）；`waitForApi()` 保留给页面内「桥迟到自己接上」用。
- **2026-10-14**：**启动期「一次判死」的代码都要能自愈** ——「推荐段」和「继续阅读」卡在桥没好时会把自己**永久藏起来**（不报错、不重来，用户只看到少两块）。现在推荐段最多补 3 次（退避 0.9/1.8/2.7s，期间留骨架）、继续阅读卡最多补 6 次 ×1.5s（拿到过一次结果就停）。回归检查 `tmp/_check_coldstart.py`：假桥故意延迟 2s 才挂方法，旧包 FAIL、现包 PASS。

- **2026-10-14**：**别在 `js_api` 上挂公开的非方法属性** —— pywebview 的 `get_functions` 拿 `dir()`+`getattr()` 递归展开，公开属性一律变成 JS 方法（`client` 412 条 / `download_dir` 300 多条），而且 `getattr` 会在注入线程里现场求值（jmcomic 客户端 0.855s）。实测：改私有名之后 funcList **447 → 35 条、0.855s → 0.000s**，桥就绪 **1.3~4.8s → ~100ms**，首页首屏 ~900ms。
- **2026-10-14**：前端两条纪律 —— ① 启动闸门 `waitForBridge()` 要等**最后一次注入安静下来**（`quietMs=400`）再放行；② 启动路径上的**读**调用走 `bridgeCall()`（被清掉的调用当场判死、自动重发；写接口不幂等，别用）。原因见下一条。
- **2026-10-14**：**桥会注两遍，第二遍会清掉在飞调用的回调**（WebView2 给 about:blank 和真页面各报一次 NavigationCompleted；先到那次的 finish.js 落在我们的文档里，对着后建的对象又跑一遍 `_createApi()`）。症状：`window.pywebview._returnValuesCallbacks.<fn>.<id> is not a function` + 那个 promise 永不 settle。回归检查 `tmp/_check_bridge_wipe.py`（真 api.js/finish.js + 假 Python 端）：修复前的包两种场景都整窗空白，现包照铺。

- **2026-10-14**：**“返回还原”只认「历史穿梭」，不认「点导航」** —— 判据用每条历史记录上那枚递增序号（`history.state.__seq`），
  不用 `popstate`：Chrome 在 hash 变化时也会派人一个 `popstate`，会把“点导航进新页面”误判成“退回来”（症状是位置停在上一页不回顶）。
- **2026-10-14**：滚动位置记忆（`scrollMemo`）**只活在这一次会话**：刷新 / 重开窗口从头看是正常预期，落盘反而会跟“新开一次想从顶部看”打架。
- **2026-10-14**：**页面自己改地址一律走 `replaceHash()`**，不要裸 `replaceState` —— 前者会把该历史记录的序号章带过去；
  裸 replace 会把章冲掉，“从详情返回这一条”就认不出来（页码能对上，滚动位置会丢）。
- **2026-10-14**：用户从体验候选里挑了前三项，**下载页那项（总占用 / 剩余空间 / 按话下载 / 导出）先砍掉**，不在本轮范围里。

## 下一步

1. 用户真窗口验收（真图源、5173 + `main.py`）：
   - **开场动画**：冷启动看描字 → 揭幕那一下首页是否已经有封面 → 字标飞进左上角顺不顺、落下后是不是 `GuZhu漫画` 一行
     （2026-10-14 定的落位）；毛玻璃开 / 关各看一次，开场那一下有没有闪白（设计稿 §3.4，**这条是唯一还没验的**）。
   - **推荐**：正常看几部、收藏两部、搜几个词 → 回首页看第一段「为你推荐」的排布与副标题（`同人 · 中文` / `作者：山田`）、点「换一批」；再清空搜索记录 + 取消全部收藏，看是否退化成「热门推荐」；把 `recommend.limit` 改成 0，看整段是不是干净地消失。
   - **角标**：首页 hero 与分类横条、分类页、搜索页、推荐段、论坛封面条上，收藏过的都有「已收藏」，没收藏的一个都没有；收藏页与详情页不该有。
   - **搜索记录**：搜几个词 → 刷新页面 / 重开窗口，chips 还在（现在读的是数据库）；点 chip 重搜、✕ 删单条、清空。
   - 顺带看上一轮的**预加载体感**、详情页两栏版式 / 章节折叠、首屏会不会再空白。
   - **本轮三项**：分类页 / 论坛翻两页 → 点进详情 → 点「返回」，看落回的是不是原来那一页（滚动位置 + 页码都在）；
     详情页点作者名 / 标签，看是不是一下按那个范围重搜；阅读器里鼠标从上边下来、从下边上来，看是不是只亮对应的那一条（中间不动）。
2. 推荐二期（`tmp/推荐算法设计.md` §10 / §11）：`related_list` **已经在用了**（详情页那排「相关作品」就是它，A3 那轮起的），
   二期是拿它当「图上的邻居」做「收藏了《X》的人也在看」；另外两个是推荐结果缓存、设置页里显示 / 调节画像
   （`get_taste_profile` 后端与 `pywebview.d.ts` 都在，只差界面）。
3. ~~A4「只看汉化」~~ —— **2026-10-14 用户定：不做**（真要做也得先引入 `impl='html'` 第二客户端，见评估 §3）。
4. ~~B3 整本离线下载~~ —— **2026-10-14 已完成**（`tmp/下载设计.md`）：`download.dir` + `/downloads` 静态根 +
   `#/downloads` + 详情页同排下载按钮。还想做的（**2026-10-14 用户定：先砍掉，本轮不做**）：下载页显示总占用 / 剩余空间、
   按话下载（现在只有整本）、导出成文件包。


4.5 ~~**首页 hero 去重**~~ —— **2026-10-14 已完成**（见上面那份改动清单）：推荐段与分类横条都不再出现 hero 那三部。
5. ~~**推荐段健壮性**~~ —— **2026-10-14 已修，并查到了真正的根因**（闸门另按方法引用判重注入、`quietMs=800`，见上面那份改动清单）：pywebview 启动会注两遍桥，第二次 `_createApi()` 重建在飞回调表 → 那些 promise 永不 settle → `await loadSettings()` 挂死、整窗空白。根因在后端 `API.client` / `API.download_dir` 是公开属性（被递归展开成 447 条、现场建客户端 0.855s，把两步窗口拉到秒级），已改私有名；前端配 `waitForBridge` 静默窗 + `bridgeCall` 重试。回归：`tmp/_check_coldstart.py`（假桥晚挂方法）、`tmp/_check_bridge_wipe.py`（模拟注两遍）。还想要的（可选）：候选池真空时兜底用榜单数据铺热度。
6. ~~开场动画~~ —— **2026-10-14 已完成**（设计 `tmp/开场动画设计.md`，调研 `tmp/开场动画调研.md`）。
   落位也已定稿：字标只换「孤竹」两字，品牌行 = `GuZhu漫画`（2026-10-14 定，代码已改，见上面那份改动清单）。
   真机只剩一件待验收：毛玻璃开着时开场那一下的底色（设计稿 §3.4）。

7. ~~**打包 P0 落码**~~ —— **2026-10-14 已完成**（见上面「打包落地」一节）：出包 + 真 exe 验收通过（见 `tmp/打包分发设计.md` §4 / §11 的原方案）：`backend/paths.py`（配置 + dist 路径统一入口）+ `backend/server.py`（本地静态服务，端口 47753 + 回退）+ `main.py` 按 `dev.use_dev_server` 选 URL + `API(base_url=...)` + `webview.start(private_mode=False, storage_path=...)`。验收：`scripts/build_exe.ps1` 出包 → 双击 → 走一遍首页 / 搜索 / 详情 / 阅读 / 最近阅读 / 设置 → 重开确认主题与偏好还在。
8. ~~**打包 P1**~~ —— **2026-10-14 已完成**（256×256 图标源图 / 单实例检测 / WebView2 缺失提示 / 日志落盘）。
9. ~~**加固 + 第四次出包（发布版）**~~ —— **2026-10-14 已完成**：见上面「第四次出包」与 `tmp/交接文档.md` §0.5
   （产物哈希 / 验收证据 / 待提交清单 / 没验证的边界）。
   别做自动更新（无签名 + 自动下 exe = 误报与安全双重坑）。

10. **发布版之后又动过前端**（品牌行落位 + 搜索页返回修复，2026-10-14）：`build_out/` 里那两个产物里的 dist 是**旧的**，
   要发给同学就重跑 `scripts/build_exe.ps1`，并重新记哈希 / 复扫（`tmp/_vt_*` 那套）。
