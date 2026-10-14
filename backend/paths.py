"""
用户目录 / 只读资源目录的唯一入口。

打成一个目录发给用户之后，代码就不再是「仓库里的几个 .py」：
  * 只读资源（前端 dist）被 PyInstaller 解到 `_MEIPASS`（即 <exe>/_internal）；
  * 用户数据（配置、数据库、缓存、下载）必须落家目录 —— 包要是被放在 Program Files，
    写进去就是只读，设置页一保存就炸，升级覆盖安装还会把用户的东西冲掉。

平台差异只许出现在这一层：将来要上 mac / Android，换的也只是这里（Android 上换成 app 私有目录），
业务代码里不许出现 `sys.platform` / `sys.frozen`。
"""
import sys
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".jmreader"
# data/ 放再生不出来的用户数据，cache/ 放随时可删的缓存（受 cache.max_size_mb 约束）
DATA_DIR = APP_DIR / "data"
DATA_DB = DATA_DIR / "app.db"
CACHE_DIR = APP_DIR / "cache"
CACHE_DB = CACHE_DIR / "cache.db"
IMG_DIR = CACHE_DIR / "images"
# WebView2 的 user data：不固定在这儿的话 pywebview 每次开窗都用临时目录，localStorage 里的
# 主题 / 榜单偏好就活不过一次重启（见 tmp/打包分发设计.md §1 第 4 条）
WEBVIEW_DIR = APP_DIR / "webview"


def is_frozen() -> bool:
    """是不是 PyInstaller 打出来的包"""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """只读资源根：冻结态 = _MEIPASS（即 <exe>/_internal），源码态 = 仓库根"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    """
    配置文件放哪：开发态继续吃仓库根的 config.yaml（改了就生效，保持手感），
    冻结态落用户目录 —— 首启写一份默认值出去，用户能直接看到、也能直接改。
    """
    return (APP_DIR / "config.yaml") if is_frozen() else (bundle_dir() / "config.yaml")


def dist_dir() -> Path:
    """前端产物：打包时 `--add-data "frontend/dist;dist"` 落到 <exe>/_internal/dist"""
    return (bundle_dir() / "dist") if is_frozen() else (bundle_dir() / "frontend" / "dist")


def resolve_download_dir(raw: Any) -> Path:
    """
    配置里的 download.dir 解析成绝对路径。

    支持 ~（cwd 不是家目录，只有 expanduser 认它）与相对路径（相对 ~/.jmreader）。
    空值回落 downloads/ —— 但配置项本身一直有默认值，正常情况下不会走到这儿。
    """
    text = str(raw or "").strip() or "downloads"
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = APP_DIR / path
    return path
