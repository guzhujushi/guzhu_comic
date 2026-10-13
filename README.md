# guzhu_comic

无广告的桌面漫画阅读器。前端基于 Vite + TypeScript，后端基于 Python（`jmcomic`），通过 PyWebView 打包为桌面应用。

## 特性

- **搜索**：关键词搜索漫画，搜索结果元数据本地缓存 1 小时
- **热门榜单**：日榜 / 周榜 / 月榜 × 全部 / 同人 / 单本 / 短篇 / 韩漫 / 美漫多维度切换
- **详情页**：封面、作者、标签、简介、热度数据与章节列表，详情缓存 24 小时
- **阅读器**：连续滚动阅读，支持键盘（←/→/Esc）与点击翻页，断点自动续读
- **历史记录**：阅读进度本地持久化，支持继续阅读
- **图片缓存**：章节图片下载并解密到本地，二次打开秒加载、支持离线阅读
- **缓存管理**：一键清除全部本地缓存

## 技术栈

| 层       | 技术                                              |
| -------- | ------------------------------------------------- |
| 前端     | Vite + HTML / CSS / TypeScript                    |
| 后端     | Python + [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) |
| 桌面封装 | PyWebView（Windows 下使用 WebView2/Chromium）      |
| 前后端桥 | PyWebView `js_api` 直调（无 HTTP 中间层）          |
| 本地存储 | SQLite（元数据 / 阅读进度）+ 文件系统（图片缓存）  |
| 图片服务 | Python `http.server` 本地静态服务（127.0.0.1）     |

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

