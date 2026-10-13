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
- [x] B5 「论坛」页（= 全站评论流 `forum_pagination`，只读、不登录）：左侧导航「论坛」+ `#/forum`，评论下面挂进本子的封面条（2026-10-13）
- [ ] A4 「只看汉化」（必须先引入 `impl='html'` 的第二客户端，见评估 §3）
- [ ] B3 整本离线下载（大工程，单独立项）
- [x] 不做：一切账号体系（登录 / 网页端收藏 / 签到 / 发评论）—— 会落地账号凭据，有隐私风险（2026-10-13 定）

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

## 下一步

1. 用户真窗口验收：详情页两栏版式 / 章节折叠 / 评论「看更多」；**B4 的心形与「收藏」页**（含空状态与卡片角上的删除）。
2. A4「只看汉化」（必须先引入 `impl='html'` 的第二客户端，见评估 §3）。
3. B3 整本离线下载（大工程，单独立项）。
