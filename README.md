# guzhu_comic

无广告的桌面漫画阅读器。前端基于 Vite + TypeScript，后端基于 Python（[JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)），通过 PyWebView 打包为桌面应用。

## 特性

- **搜索**：关键词搜索漫画，搜索结果元数据本地缓存 1 小时
- **热门榜单**：日榜 / 周榜 / 月榜 × 全部 / 同人 / 单本 / 短篇 / 韩漫 / 美漫多维度切换
- **详情页**：封面、作者、标签、简介、热度数据与章节列表，详情缓存 24 小时
- **开始 / 继续阅读**：详情页顶部按阅读记录显示「开始阅读」或「继续阅读 · 第 N 页」，上次读到的那一话在章节列表里描蓝
- **阅读器**：连续滚动 / 单页翻页两种模式，支持键盘（←/→/↑/↓/PageUp/PageDown/Esc）与点击两侧翻页；翻页时写进度，退出（返回按钮 / 关窗口）也会再确认一次
- **阅读工具栏**：默认藏起来，鼠标动一下才出来（滚轮 / 方向键不算），停手两秒多自己收起；里面有上一章 / 章节列表 / 下一章和阅读设置，按 `M` 也能手动唤出
- **阅读设置**：工具栏里直接改阅读模式、背景色、页间距、自动滚屏，改完立即生效；自动滚屏开着时工具栏会多出一个暂停键，滚轮一碰就停
- **最近阅读**：导航栏直达，按最近读过的顺序列出漫画（同一部只占一条），卡片上标着读到第几页
- **设置页**：`config.yaml` 里的常用项直接在窗口里改，带缓存占用显示与手动整理
- **阅读进度**：本地持久化，属于用户数据，清缓存不会动它
- **图片缓存**：章节图下载并解密到本地，二次打开秒加载、支持离线阅读
- **缓存管理**：上限默认 2G，后台定时按「最久没看过」整话清理，也能一键清空

## 技术栈

| 层       | 技术                                              |
| -------- | ------------------------------------------------- |
| 前端     | Vite + HTML / CSS / TypeScript                    |
| 后端     | Python + [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) |
| 桌面封装 | PyWebView（Windows 下使用 WebView2/Chromium）      |
| 前后端桥 | PyWebView `js_api` 直调（无 HTTP 中间层）          |
| 本地存储 | SQLite（`data/app.db` 阅读进度、`cache/cache.db` 接口元数据）+ 文件系统（`cache/images` 章节图） |
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
| 热门     | `#/popular`                     | 榜单                                                     |
| 搜索     | `#/search`                      | 关键词搜索                                               |
| 最近阅读 | `#/history`                     | 一部漫画一条（取最近读的那一话），按时间倒序，点卡片进详情页 |
| 设置     | `#/settings`                    | 改配置、看缓存占用、立即整理 / 清空缓存                  |
| 详情     | `#/album?id=`                   | 漫画信息 + 章节列表 + 开始 / 继续阅读                    |
| 阅读器   | `#/read?photo_id=&album_id=`    | 连续滚动 / 单页翻页，翻页时写进度；顶部工具栏默认隐藏，鼠标晃动唤出 |

## 数据与缓存

```text
%USERPROFILE%\.jmreader\
├── data\
│   └── app.db                # 用户数据：阅读进度（history 表），再生不出来
└── cache\
    ├── cache.db              # 接口元数据：搜索 / 榜单 / 详情 / 章节图列表
    └── images\<photo_id>\    # 章节图（已解密），一话一个目录
```

- `data/` 只在翻页时写入，清缓存 / 整理缓存都不会碰它。
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
| `dev.url`                 | `http://localhost:5173` | 窗口加载地址（Vite 开发服务器或 `dist/index.html`）        |
| `dev.debug`               | `true`                | 调试模式，打开后可以 F12 / 右键检查                          |
| `reader.restore_progress` | `true`                | 进章节时自动回到上次那一页                                   |
| `reader.click_to_page`    | `true`                | 点击左右两侧翻页，关掉后只剩滚轮 / 方向键                    |
| `reader.mode`             | `webtoon`             | 连续滚动 webtoon / 单页翻页 single，阅读器里改是立即生效      |
| `reader.background`       | `dark`                | dark / black / gray / light                                   |
| `reader.page_gap`         | `0`                   | 连续滚动时每张图之间留的空隙（像素），最大 64                 |
| `reader.auto_scroll`      | `0`                   | 自动滚屏速度（像素/秒），0 = 关；只在连续滚动模式有效         |
| `download.workers`        | `8`                   | 章节图下载并发数，太大容易被图源限速                         |
| `cache.photo_ttl`         | `86400`               | 章节图列表缓存时长（秒）                                     |
| `cache.album_ttl`         | `86400`               | 漫画详情缓存时长（秒）                                       |
| `cache.search_ttl`        | `3600`                | 搜索缓存时长（秒）                                           |
| `cache.ranking_ttl`       | `3600`                | 榜单缓存时长（秒）                                           |
| `cache.max_size_mb`       | `2048`                | 缓存上限（MB），`0` = 不限                                   |
| `cache.cleanup_interval`  | `600`                 | 后台清理间隔（秒）                                           |

## 目录结构

```text
guzhu_comic/
├── main.py                 # 入口：读 config.yaml 开窗，把 API 挂成 js_api
├── config.yaml             # 配置（设置页读写）
├── backend/
│   ├── api.py              # 全部 js_api：搜索 / 榜单 / 详情 / 章节图 / 进度 / 缓存
│   └── config.py           # config.yaml 读写，缺的键用默认值补齐
└── frontend/
    └── src/
        ├── main.ts         # 导航 + 路由注册
        ├── router.ts       # hash 路由
        ├── settings.ts     # 前端读配置（进程内缓存一份）
        ├── webstatus.ts    # 等 pywebview 把桥注入好
        ├── pywebview.d.ts  # js_api 的类型声明
        ├── pages/          # popular / search / detail / reader / history / settings
        └── components/     # album-card、album-list
```