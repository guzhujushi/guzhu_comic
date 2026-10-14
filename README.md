# guzhu_comic

无广告的桌面漫画阅读器。前端基于 Vite + TypeScript，后端基于 Python（[JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)），通过 PyWebView 打包为桌面应用。

## 特性

- **搜索**：首页顶部有一个毛玻璃搜索入口（按 `/` 也能进），搜索页整页做成一整块毛玻璃，进去光标直接落在输入框上；搜索结果元数据本地缓存 1 小时
- **热门榜单**：最上面三部做成弧形轮播（当前分类最火的三部）；下面一条分类标签条（全部 / 同人 / 单本 / 短篇 / 韩漫 / 美漫），当前那个标签和下面的面板同色连成一块；首页面板里按分类铺横条，**每个分类只铺一行**（一行放几张随宽度变），行头左边分类名、右边「更多」进该分类页；分类页同样有标签条与 hero（hero 换成该分类前三），下面铺该分类的整页列表与「加载更多」；日 / 周 / 月与排序两页共用，选择会记住
- **详情页**：封面、作者、标签、简介、热度数据（观看 / 喜欢 / 评论数）、发布日期与更新日期、相关作品，以及可折叠的章节列表；右侧是只读评论区（剧透默认盖住）；详情缓存 24 小时
- **开始 / 继续阅读**：详情页顶部按阅读记录显示「开始阅读」或「继续阅读 · 第 N 页」，上次读到的那一话在章节列表里描蓝
- **阅读器**：整屏沉浸，顶部一条细进度线常驻；连续滚动 / 单页翻页两种模式，支持键盘（←/→/空格/Home/End/↑/↓/PageUp/PageDown/Esc）与点击两侧翻页，点屏幕中间收放工具条；翻页时写进度，退出（返回按钮 / 关窗口）也会再确认一次
- **阅读工具栏**：上下两条，默认都藏起来，鼠标动一下才出来（滚轮 / 方向键不算），停手两秒多自己收起；上面只有返回和标题 + 页码，下面是上一话 / 目录 / 下一话 / 设置（自动滚屏开着时顶部多一个暂停键），按 `M` 也能手动唤出
- **目录与阅读设置**：目录是带编号的底部浮层（几百话也找得到，当前话高亮并自动滚到眼前），设置浮层里改阅读模式、背景色、图片宽度、页间距、自动滚屏，改完立即生效；自动滚屏开着时顶部会多出一个暂停键，滚轮一碰就停
- **话末续读**：一话读完在图末给一张「下一话 · 第 N 话」的大按钮（单页模式浮在最后一页上），换话后角落提示一句，不用自己摸回目录找
- **首页轮播**：当前榜单最火的三部做成横向大卡片，摆成弧形自己转（鼠标停上去就停），点两侧的转到中间、点中间那张才进详情
- **论坛**：全站评论流（只读，**不需要登录**），一条条往下翻、点「加载更多」接着要；每条评论下面挂一个「来自《本子名》」的封面条，点它直接进详情。标题是后台补的（先显示 `JM<id>`，拿到缓存里的详情标题再换掉），剧透评论默认糊住
- **左侧导航**：固定侧栏 + 品牌，窗口窄了自动只剩图标，当前页的图标会变形
- **设置页**：`config.yaml` 里的常用项直接在窗口里改，带缓存占用显示与手动整理
- **阅读进度**：本地持久化，属于用户数据，清缓存不会动它
- **本地收藏**：详情页右上角一颗心，点一下即收藏（失败会自己翻回来）；「收藏」页按收藏时间倒序列出，卡片角上能取消。存在本机 `data/app.db`，**与图源账号无关、不需要登录**，清缓存也不会丢
- **图片缓存**：章节图下载并解密到本地，二次打开秒加载、支持离线阅读
- **缓存管理**：上限默认 2G，后台定时按「最久没看过」整话清理，也能一键清空
- **窗口毛玻璃**：Windows 上窗口整体半透明，底层交给系统 DWM 画亚克力，桌面内容由系统模糊（`window.glass` 选 none / mica / acrylic / tabbed，`window.glass_opacity` 控透度）
- **加载与动效**：列表先铺骨架卡片（蓝色呼吸光晕 + 从右下扫到左上的光带），搜到 / 保存完的按钮图标会变形反馈；开窗不等图源连接（客户端后台预热），首屏某一块没拉下来只降级成那一块的提示并自动重试，窗口从后台回到前台时也会自己补一次，不会停在空白页
- **视觉**：暗色分层取自 [Raycast 设计系统](https://github.com/VoltAgent/awesome-design-md)——表面阶梯（画布 → 卡片）配 1px 发丝线做层级，不靠投影；主操作用白底黑字，蓝色只给加载 / 焦点 / 阅读进度；阅读器设置里有键帽样式的快捷键提示

## 技术栈

| 层       | 技术                                              |
| -------- | ------------------------------------------------- |
| 前端     | Vite + HTML / CSS / TypeScript                    |
| 图标动效 | [morphicons](https://morphicons.com)（描边图标变形）+ [lucide](https://lucide.dev)（图标数据） |
| 设计系统 | [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) 里的 Raycast DESIGN.md（暗色分层 + 发丝线 + 键帽） |
| 后端     | Python + [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) |
| 桌面封装 | PyWebView（Windows 下使用 WebView2/Chromium），窗口毛玻璃走 DWM 亚克力 |
| 前后端桥 | PyWebView `js_api` 直调（无 HTTP 中间层）          |
| 本地存储 | SQLite（`data/app.db` 阅读进度 + 本地收藏、`cache/cache.db` 接口元数据）+ 文件系统（`cache/images` 章节图） |
| 图片服务 | Python `http.server` 本地静态服务（127.0.0.1，端口随机） |

## 环境要求

- Windows 10 / 11（需 WebView2 运行时，Win11 自带）
- Python 3.12+
- Node.js 18+

## 快速开始

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 安装前端依赖
npm --prefix frontend install

# 3. 启动前端开发服务器（终端 1）
npm --prefix frontend run dev

# 4. 启动桌面应用（终端 2）
python main.py
```

`config.yaml` 里的 `dev.url` 就是窗口加载的地址，默认指向 Vite 开发服务器；前端 `npm run build` 之后也可以改成打包出来的 `dist/index.html`。

## 页面

| 页面     | 路由                            | 说明                                                     |
| -------- | ------------------------------- | -------------------------------------------------------- |
| 热门     | `#/popular`                     | 首页轮播（全部最火三部）+ 分类标签条 + 各分类一行（右边「更多」进分类页） |
| 分类     | `#/category?c=`                 | 某个分类的榜单页：hero 是该分类前三，下面是整页列表，「加载更多」 |
| 搜索     | `#/search`                      | 关键词搜索，整页是一块毛玻璃外壳                          |
| 论坛     | `#/forum`                      | 全站评论流，只读不登录；每条评论挂一个进对应本子的封面条  |
| 最近阅读 | `#/history`                     | 一部漫画一条（取最近读的那一话），按时间倒序，点卡片进详情页 |
| 收藏     | `#/favorites`                   | 本地收藏，按收藏时间倒序，卡片角上可取消收藏              |
| 设置     | `#/settings`                    | 改配置、看缓存占用、立即整理 / 清空缓存                  |
| 详情     | `#/album?id=`                   | 漫画信息 + 章节列表 + 开始 / 继续阅读                    |
| 阅读器   | `#/read?photo_id=&album_id=`    | 连续滚动 / 单页翻页，翻页时写进度；上下两条工具条默认隐藏，鼠标晃动唤出 |

## 数据与缓存

```text
%USERPROFILE%\.jmreader\
├── data\
│   └── app.db                # 用户数据：阅读进度（history 表）+ 本地收藏（favorite 表），再生不出来
└── cache\
    ├── cache.db              # 接口元数据：搜索 / 榜单 / 详情 / 章节图列表
    └── images\<photo_id>\    # 章节图（已解密），一话一个目录
```

- `data/` 只在翻页 / 收藏时写入，清缓存 / 整理缓存都不会碰它。
- `cache/` 里的东西全是可再生的：删掉只是下次重新请求、重新下载。
- 上限 `cache.max_size_mb` 默认 `2048`（2G），`0` 表示不限；占用按整个 `cache/` 目录算，设置页能看到当前用量。
- 后台线程每 `cache.cleanup_interval` 秒（默认 600）检查一次，超过上限就从最久没看过的章节开始**整话**删，一直压到上限的 90%；正在看的章节和正在下载的章节留到最后才删。

## 配置项

设置页能改的都在这里，保存后写回 `config.yaml`；标了「重启生效」的要重开窗口才用得上。

| 键                        | 默认                  | 说明                                                         |
| ------------------------- | --------------------- | ------------------------------------------------------------ |
| `window.title`            | `Guzhu Comic`         | 窗口标题                                                     |
| `window.width`            | `1200`                | 初始窗口宽度                                                 |
| `window.height`           | `800`                 | 初始窗口高度                                                 |
| `window.min_size`         | `[800, 600]`          | 最小窗口尺寸（宽、高）                                       |
| `window.glass`            | `acrylic`             | 窗口毛玻璃：none / mica / acrylic / tabbed，重启生效（Win11 22H2+ 才有效果） |
| `window.glass_opacity`    | `0.92`                | 窗口整体不透明度 0.35–1，越小越透，重启生效                   |
| `dev.url`                 | `http://localhost:5173` | 窗口加载地址（Vite 开发服务器或 `dist/index.html`）        |
| `dev.debug`               | `true`                | 调试模式，打开后可以 F12 / 右键检查                          |
| `reader.restore_progress` | `true`                | 进章节时自动回到上次那一页                                   |
| `reader.click_to_page`    | `true`                | 点击左右两侧翻页，关掉后只剩滚轮 / 方向键                    |
| `reader.mode`             | `webtoon`             | 连续滚动 webtoon / 单页翻页 single，阅读器里改是立即生效      |
| `reader.background`       | `dark`                | dark / black / gray / light                                   |
| `reader.page_gap`         | `0`                   | 连续滚动时每张图之间留的空隙（像素），最大 64                 |
| `reader.width`            | `1080`                | 阅读器图片列最大宽度（像素），`0` = 铺满窗口                 |
| `reader.auto_scroll`      | `0`                   | 自动滚屏速度（像素/秒），0 = 关；只在连续滚动模式有效         |
| `detail.chapters_collapse` | `20` | 章节数超过这个就先折叠（0 = 全部展开）；折叠时给「展开全部」和「跳到上次读到的那话」两个按钮 |
| `detail.comment_preview` | `5` | 详情页右侧评论区先显示几条（0 = 不显示评论区）；评论只读，不需要登录 |
| `download.workers`        | `8`                   | 章节图下载并发数，太大容易被图源限速                         |
| `cache.photo_ttl`         | `86400`               | 章节图列表缓存时长（秒）                                     |
| `cache.album_ttl`         | `86400`               | 漫画详情缓存时长（秒）                                       |
| `cache.search_ttl`        | `3600`                | 搜索缓存时长（秒）                                           |
| `cache.ranking_ttl`       | `3600`                | 榜单缓存时长（秒）                                           |
| `cache.comment_ttl`       | `600`                 | 评论缓存时长（秒），评论更新快所以默认短一些                   |
| `cache.max_size_mb`       | `2048`                | 缓存上限（MB），`0` = 不限                                   |
| `cache.cleanup_interval`  | `600`                 | 后台清理间隔（秒）                                           |

## 目录结构

```text
guzhu_comic/
├── main.py                 # 入口：读 config.yaml 开窗，把 API 挂成 js_api
├── config.yaml             # 配置（设置页读写）
├── backend/
│   ├── api.py              # 全部 js_api：搜索 / 榜单 / 详情 / 评论 / 章节图 / 进度与收藏 / 缓存
│   ├── config.py           # config.yaml 读写，缺的键用默认值补齐
│   └── glass.py            # Windows 窗口毛玻璃：DWM 亚克力 + 窗口透明度
└── frontend/
    └── src/
        ├── main.ts         # 导航 + 路由注册
        ├── router.ts       # hash 路由
        ├── settings.ts     # 前端读配置（进程内缓存一份）
        ├── webstatus.ts    # 等 pywebview 把桥注入好
        ├── pywebview.d.ts  # js_api 的类型声明
        ├── pages/          # board（热门/分类共用）/ popular / category / search / forum / detail / reader / history / favorites / settings
        └── components/     # album-card、album-list
```
