"""
安卓壳的 Python 入口（P2：Kotlin 壳 → Chaquopy → 本地静态服务 → WebView 加载）。

Kotlin 侧的调用顺序（`android/app/src/main/java/cn/guzhujushi/comic/MainActivity.kt`）：

    Python.start(AndroidPlatform(this))
    Python.getInstance().getModule("android_boot")
          .callAttr("start", filesDir.absolutePath, dist.absolutePath)   -> base url
    webView.loadUrl(url)

为什么单开一个文件、而不是让 Activity 直接调 `backend.server`：

  * `backend/` 是跨平台业务代码，安卓那点东西（私有目录、assets 解包）不许渗进去 ——
    平台差异收在 `backend/paths.py` 与这里；
  * 端口 / extra_roots / overlay 与桌面 `main.py._pick_url` 保持**同一套口径**：两边跑的是
    同一个服务、同一份前端，桌面怎么调的这里照着调（那边是那份口径的出处）。
"""
import os


def start(app_dir: str, dist_dir: str) -> str:
    """
    起本地静态服务，返回 base url（形如 `http://127.0.0.1:47753`）。失败就把异常抛给 Kotlin。

    `app_dir` / `dist_dir` 由壳递进来（`context.filesDir` 与解包出来的前端根）。**必须在
    import `backend` 之前**写进环境变量：`backend.paths` 是在 import 期就把 APP_DIR / dist_dir
    算死的（模块级常量，全项目都直接读），晚一步就赶不上。
    """
    os.environ["GUZHU_APP_DIR"] = app_dir
    os.environ["GUZHU_DIST_DIR"] = dist_dir

    from backend import logging_setup, paths
    from backend.config import load_config
    from backend.server import DEFAULT_PORT, start_static_server

    log_path = logging_setup.setup()
    config = load_config()

    dist = paths.dist_dir()
    log_path_text = str(log_path) if log_path else "装不上"
    print(f"[android] 用户目录 {paths.APP_DIR}", flush=True)
    print(f"[android] 前端根 {dist}（在={dist.is_dir()}）", flush=True)
    print(f"[android] 日志 {log_path_text}", flush=True)

    if not (dist / "index.html").is_file() and not (paths.WEB_DIR / "index.html").is_file():
        # 不拦：服务照样起，页面会是 404 —— 但要让人一眼看到是"前端没解出来"而不是别的问题
        print(f"[android] 前端产物不在：{dist}（壳那边的 assets 解包没跑成功？）", flush=True)

    base = start_static_server(
        dist,
        {
            "/images": paths.IMG_DIR,
            "/downloads": paths.resolve_download_dir(config["download"]["dir"]),
        },
        _port(config, DEFAULT_PORT),
        overlay=paths.WEB_DIR,      # 热更覆盖层：有就用它（跟桌面同一条路）
    )
    print(f"[android] 本地服务已起：{base}", flush=True)
    return base


def _port(config: dict, fallback: int) -> int:
    """与 `main.py._port` 同一套口径：用户手改成非法值也不该拦住启动"""
    try:
        n = int(float(config["server"]["port"]))
    except (KeyError, TypeError, ValueError):
        return fallback
    return n if 1024 <= n <= 65535 else fallback