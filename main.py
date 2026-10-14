import logging
import sys
import threading

import webview

from backend import desktop, glass, logging_setup, paths, single_instance, updater, webview2
from backend.api import API
from backend.config import load_config, save_config
from backend.server import DEFAULT_PORT, start_static_server


def _alert(text: str) -> None:
    """
    出事了给一句人话。

    `--windowed` 的包里没有控制台（stdout 指向 nul），只 print 等于什么都没跟用户说 ——
    用户看到的就是"双击了没反应"。MessageBoxW 是这里唯一的零依赖出口（tkinter 已被裁掉）。
    """
    print(f"[fatal] {text}", flush=True)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "孤竹漫画", 0x10)
    except Exception:
        pass


def _port(config: dict) -> int:
    """配置里的静态服务端口；用户手改成一个非法值也不该拦住开窗"""
    try:
        n = int(float(config["server"]["port"]))
    except (KeyError, TypeError, ValueError):
        return DEFAULT_PORT
    return n if 1024 <= n <= 65535 else DEFAULT_PORT


def _prepare_user_dir() -> None:
    """
    用户目录该有的先建出来：配置、WebView2 的 user data 都落在这儿。

    冻结态首启还要写一份默认 config.yaml 出去 —— 写出来了用户才知道设置存哪儿、也才能手改。
    写不动（磁盘满 / 目录只读）只提示一句：配置读取本身有默认值兜底，不该为这个把窗口拦下。
    """
    try:
        paths.APP_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[paths] 用户目录建不出来（不影响使用）: {e}", flush=True)
        return
    if paths.is_frozen() and not paths.config_path().exists():
        try:
            save_config(load_config())
            print(f"[config] 首次运行，默认配置写到 {paths.config_path()}", flush=True)
        except OSError as e:
            print(f"[config] 默认配置写不进去（不影响使用）: {e}", flush=True)


def _pick_url(config: dict) -> tuple[str, str | None]:
    """
    选这次加载哪个地址，返回 (url, base_url)。

    源码态且 dev.use_dev_server 开着 → 走 vite（改前端不用重打包）；其余一律起本地静态服务喂
    frontend/dist —— 打包后没有 Node、没有 vite，只有这一条路。base_url 回给 API，图片就挂在
    同一个端口上（页面与图同源）。
    """
    dev_cfg = config["dev"]
    if not paths.is_frozen() and bool(dev_cfg.get("use_dev_server", False)):
        return str(dev_cfg["url"]), None

    dist = paths.dist_dir()
    overlay = paths.WEB_DIR          # 前端热更新下来的那份（有就用它，见 backend/updater.py）
    if not (dist / "index.html").exists() and not (overlay / "index.html").exists():
        raise RuntimeError(f"前端产物不在：{dist}"
                           "（源码态先跑 npm run build；包被拆过的话 dist 要跟 exe 一起在 _internal 里）")
    base = start_static_server(
        dist,
        {
            "/images": paths.IMG_DIR,
            "/downloads": paths.resolve_download_dir(config["download"]["dir"]),
        },
        _port(config),
        overlay=overlay,
    )
    return base + "/", base


def _gate(config: dict) -> bool:
    """
    开窗前的两道闸。返回 False = 这次不开窗（已经提示过用户了）。

    ① 单实例：已经有一个在跑就把那个拉到前台 —— 两个实例会抢同一个端口、同一份缓存目录，
       而且 user data 目录被两个进程同时开着，WebView2 自己也会闹脾气。
    ② WebView2 Runtime：缺了 pywebview 起不来，用户只会看到一个白窗口，所以先查、先说话。
    """
    if not single_instance.acquire():
        title = str(config["window"]["title"])
        logging.getLogger("app").warning("已经有一个实例在跑，这次不再开窗")
        hit = single_instance.focus_existing(title)
        _alert("孤竹漫画已经在运行了，" + ("那个窗口已经切到前面。" if hit else "去任务栏找一下它的窗口。"))
        return False

    if not webview2.installed():
        logging.getLogger("app").error("缺 WebView2 运行时，窗口开不出来")
        _alert("这台机器还缺 WebView2 运行时，窗口显示不出来。\n\n"
               "它是微软的组件，装一次就行（免费，约 2 MB，装完自动更新）。\n"
               "点「确定」后会自动打开下载页；装好再双击本程序即可。")
        try:
            import webbrowser
            webbrowser.open(webview2.DOWNLOAD_URL)
        except Exception as e:
            print(f"[webview2] 下载页没打开（地址在弹窗里）: {e}", flush=True)
        return False
    return True


def _banner(config: dict, url: str, base: str | None, log_path) -> None:
    """
    开机那几行日志：用户反馈问题时，光凭它们就能定位大半 —— 是不是打包态、配置读的哪一份、
    页面加载的哪个地址（vite 还是包内 dist）。
    """
    log = logging.getLogger("app")
    log.info("孤竹漫画启动：frozen=%s python=%s", paths.is_frozen(), sys.version.split()[0])
    log.info("配置：%s", paths.config_path())
    log.info("加载地址：%s（图片 base=%s）", url, base or "由 API 自己起一个服务")
    log.info("前端来源：%s（热更新覆盖层%s）", paths.web_dist_dir(),
             "在用" if paths.WEB_DIR.is_dir() else "还没有")
    log.info("窗口：%sx%s 毛玻璃=%s 调试=%s 日志=%s",
             config["window"]["width"], config["window"]["height"],
             config["window"]["glass"], config["dev"]["debug"], log_path or "装不上（磁盘 / 权限）")


def main() -> None:
    # 第一件事就是装日志：后面每一步（包括 _prepare_user_dir 里的失败）都要留痕
    log_path = logging_setup.setup()
    _prepare_user_dir()
    config = load_config()
    window_cfg = config["window"]
    dev_cfg = config["dev"]
    if not _gate(config):
        return
    # 上一次开窗如果没能起来（前端被换坏了 / 页面白着），这次开窗前先把它撤掉 ——
    # 详见 backend/updater.py 的 review_boot：用户不用自己去删 ~/.jmreader/web
    rolled = updater.review_boot()
    if rolled["note"]:
        _alert(rolled["note"])

    url, base = _pick_url(config)
    _banner(config, url, base, log_path)
    desktop.sync_autostart(config)     # 开机自启：配置与注册表对一遍账

    api = API(base_url=base)

    # 窗口位置与大小：开着"记住"就用上次的（摆到屏幕外了只沿用大小，见 desktop.geometry_kwargs）
    geometry = desktop.geometry_kwargs(config)
    window = webview.create_window(
        title=window_cfg["title"],
        url=url,
        js_api=api,
        width=geometry["width"],
        height=geometry["height"],
        x=geometry.get("x"),
        y=geometry.get("y"),
        min_size=tuple(window_cfg["min_size"]),
        # 闪屏底色：WebView 把页面画出来之前先垫这个色。不传的话默认是白，开窗那一下会闪白 ——
        # 而"闪白"发生在我们的 HTML 之前，内联闪屏救不了它。注意毛玻璃开着（transparent）时
        # pywebview 走透明分支，这个参数会被忽略（见 winforms.py），那时只能靠首帧够快。
        background_color="#07080a",
        transparent=glass.enabled(window_cfg),   # 页面自带透明度，底交给 DWM 的亚克力
    )

    desktop.watch_geometry(window, config)       # 关窗那一刻记下位置与大小
    # 用的是热更新那份前端吗？是就记一笔"等它报到"，前端起来后会调 notify_booted()；
    # 30 秒还没报到 = 这份前端是坏的，下次开窗自动撤掉（review_boot）
    if updater.mark_boot():
        threading.Thread(target=updater.boot_watchdog, daemon=True, name="boot-watch").start()

    webview.start(
        debug=dev_cfg["debug"],
        # 默认 private_mode=True 会把 WebView2 的 user data 丢进临时目录 → localStorage
        # （主题、榜单 / 搜索偏好）每次开窗都是新的。固定到用户目录才留得住。
        private_mode=False,
        storage_path=str(paths.WEBVIEW_DIR),
        func=lambda: (glass.apply(window, window_cfg), desktop.setup(window, config)),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:      # 开窗前的任何意外，都不该只给用户留下一片安静
        _alert(f"启动失败：{exc}")
        raise
