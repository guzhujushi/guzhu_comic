"""
用户目录 / 只读资源目录的唯一入口。

打成一个目录发给用户之后，代码就不再是「仓库里的几个 .py」：
  * 只读资源（前端 dist）被 PyInstaller 解到 `_MEIPASS`（即 <exe>/_internal）；
  * 用户数据（配置、数据库、缓存、下载）必须落家目录 —— 包要是被放在 Program Files，
    写进去就是只读，设置页一保存就炸，升级覆盖安装还会把用户的东西冲掉。

平台差异只许出现在这一层：将来要上 mac / Android，换的也只是这里（Android 上换成 app 私有目录），
业务代码里不许出现 `sys.platform` / `sys.frozen`。

**安卓（Chaquopy）已接进来（2026-10-15，P2）**：三处根全落 app 私有目录 ——
`APP_DIR = <app filesDir>`（`/data/user/0/<包名>/files`，卸载即清）；前端产物由壳从 APK 的
`assets/web/` 整块解到 `APP_DIR/dist`（assets 是只读 zip，`http.server` 读不了里面）。
桌面那条路一个字节都没动。
"""
import os
import sys
from pathlib import Path
from typing import Any, Optional


def _android_files_dir() -> Optional[Path]:
    """
    安卓（Chaquopy）下 app 私有目录；不在安卓上返回 None。

    认平台靠「`java` 模块在不在」—— 那是 Chaquopy 注进来的，桌面 / 服务器上根本没有。
    不去猜 `sys.platform`：安卓上它也是 `'linux'`，跟桌面的 linux 分不开。

    壳（android_boot.py / MainActivity）本来就会用 `GUZHU_APP_DIR` 把目录递进来，这里是兜底
    （比如有人从 chaquopy console 里手起 Python）。
    """
    try:
        from java import jclass
    except ImportError:
        return None
    try:
        app = jclass("com.chaquo.python.Python").getPlatform().getApplication()
        return Path(str(app.getFilesDir().getAbsolutePath()))
    except Exception:
        # 认得出是安卓但取不到目录：宁可退回家目录，也不要在这儿把 import 打断
        return None


# 壳递进来的（安卓）——必须在 import 期就拿到，所以由 android_boot 在 import backend 之前写环境变量
_INJECTED_APP_DIR = (os.environ.get("GUZHU_APP_DIR") or "").strip()
_INJECTED_DIST_DIR = (os.environ.get("GUZHU_DIST_DIR") or "").strip()

_ANDROID_DIR = Path(_INJECTED_APP_DIR) if _INJECTED_APP_DIR else _android_files_dir()

APP_DIR = _ANDROID_DIR if _ANDROID_DIR is not None else (Path.home() / ".jmreader")
# data/ 放再生不出来的用户数据，cache/ 放随时可删的缓存（受 cache.max_size_mb 约束）
DATA_DIR = APP_DIR / "data"
DATA_DB = DATA_DIR / "app.db"
CACHE_DIR = APP_DIR / "cache"
CACHE_DB = CACHE_DIR / "cache.db"
IMG_DIR = CACHE_DIR / "images"
# 前端热更新的覆盖层：包内 dist 是只读的（Program Files / 只读盘都可能有），所以"更新下来的
# 前端"放用户目录，静态服务每请求解析一次 —— 用哪个根由这里说了算（见 web_dist_dir）。
WEB_DIR = APP_DIR / "web"

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

    安卓一律落私有目录：包里那份（`backend/` 在 APK 里的位置）是只读的。
    """
    if _ANDROID_DIR is not None:
        return APP_DIR / "config.yaml"
    return (APP_DIR / "config.yaml") if is_frozen() else (bundle_dir() / "config.yaml")


def dist_dir() -> Path:
    """
    前端产物：打包时 `--add-data "frontend/dist;dist"` 落到 <exe>/_internal/dist
    源码态 = 仓库的 frontend/dist。

    安卓：APK 里的 `assets/web/` 是只读 zip，起服务读不了，所以由壳在启动时整块解到私有目录，
    这里指的就是解出来的那份（解包在 `MainActivity.extractAssets`）。
    """
    if _INJECTED_DIST_DIR:
        return Path(_INJECTED_DIST_DIR)
    if _ANDROID_DIR is not None:
        return APP_DIR / "dist"
    return (bundle_dir() / "dist") if is_frozen() else (bundle_dir() / "frontend" / "dist")


def web_dist_dir() -> Path:
    """
    这次该喂哪一份前端：用户目录里的覆盖层（热更新下来的）**优先**，没有就用包内那份。

    每请求调用一次（见 backend/server.py），所以更新完只要刷新页面就生效，不用重启窗口。
    """
    if (WEB_DIR / "index.html").is_file():
        return WEB_DIR
    return dist_dir()


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