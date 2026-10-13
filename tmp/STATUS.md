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
- [ ] A4 「只看汉化」（必须先引入 `impl='html'` 的第二客户端，见评估 §3）
- [ ] B3 整本离线下载（大工程，单独立项）
- [x] 不做：一切账号体系（登录 / 网页端收藏 / 签到 / 发评论）—— 会落地账号凭据，有隐私风险（2026-10-13 定）

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

## 验证记录（2026-10-13）

B4（后端真调用，21 项全过；脚本 `tmp/_b4测试.py` 跑完已删）

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

## 决策记录

- **2026-10-13**：文档按用户要求放 `tmp/`，不建 `docs/` 与根 `STATUS.md`。
- **2026-10-13**：一切需要登录 / 落盘账号凭据的能力都不做（隐私风险）；收藏改做本地版（B4）。
- **2026-10-13**：详情页的行为（折叠阈值、评论条数）都进 `config.yaml`，不留硬编码；新增配置严格按 5 处同步。
- **2026-10-13**：收藏态别塞进 `album:<id>` 详情缓存（24h TTL），要单独查本地表（B4 已按这条做：`is_favorite` 每次进详情现查）。
- **2026-10-13**：收藏表放 `data/`（用户数据），不放 `cache/`；收藏行里的 `title` / `cover_url` 是加收藏那一刻的快照，图源换线路后封面可能失效 —— 换回线上的实时地址要每次请求详情，不划算，先接受这个代价。
- **2026-10-13**：心形做"乐观更新 + 失败回滚"，`toggle_favorite` 返回切换后的状态，前端以它为准（不靠本地猜）。
- **2026-10-13**：详情缓存里不放绝对封面地址（交接文档 §5.7）；代价是浏览器 HTTP 缓存命中率下降。
- **2026-10-13**：排序对外只暴露语义名，jmcomic 短码不外泄。
- **2026-10-13**：页面上的临时选择走 localStorage，不进 `config.yaml`。
- **2026-10-13**：确认「只看汉化」不能靠 `sub_category` 直接接（`JmApiClient` 静默忽略），需引入 `impl='html'` 第二客户端。
- **2026-10-13**：`get_meta_data()` 返回 HTTP 客户端元数据，不是图源版本；要版本号用 `JmModuleConfig.APP_VERSION`。

## 下一步

1. 用户真窗口验收：详情页两栏版式 / 章节折叠 / 评论「看更多」；**B4 的心形与「收藏」页**（含空状态与卡片角上的删除）。
2. A4「只看汉化」（必须先引入 `impl='html'` 的第二客户端，见评估 §3）。
3. B3 整本离线下载（大工程，单独立项）。
