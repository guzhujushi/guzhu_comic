import webview

from backend import glass, paths, single_instance, webview2
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
    if not (dist / "index.html").exists():
        raise RuntimeError(f"前端产物不在：{dist}"
                           "（源码态先跑 npm run build；包被拆过的话 dist 要跟 exe 一起在 _internal 里）")
    base = start_static_server(
        dist,
        {
            "/images": paths.IMG_DIR,
            "/downloads": paths.resolve_download_dir(config["download"]["dir"]),
        },
        _port(config),
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
        hit = single_instance.focus_existing(title)
        _alert("孤竹漫画已经在运行了，" + ("那个窗口已经切到前面。" if hit else "去任务栏找一下它的窗口。"))
        return False

    if not webview2.installed():
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


def main() -> None:
    _prepare_user_dir()
    config = load_config()
    window_cfg = config["window"]
    dev_cfg = config["dev"]
    if not _gate(config):
        return
    url, base = _pick_url(config)

    api = API(base_url=base)

    window = webview.create_window(
        title=window_cfg["title"],
        url=url,
        js_api=api,
        width=window_cfg["width"],
        height=window_cfg["height"],
        min_size=tuple(window_cfg["min_size"]),
        # 闪屏底色：WebView 把页面画出来之前先垫这个色。不传的话默认是白，开窗那一下会闪白 ——
        # 而"闪白"发生在我们的 HTML 之前，内联闪屏救不了它。注意毛玻璃开着（transparent）时
        # pywebview 走透明分支，这个参数会被忽略（见 winforms.py），那时只能靠首帧够快。
        background_color="#07080a",
        transparent=glass.enabled(window_cfg),   # 页面自带透明度，底交给 DWM 的亚克力
    )

    webview.start(
        debug=dev_cfg["debug"],
        # 默认 private_mode=True 会把 WebView2 的 user data 丢进临时目录 → localStorage
        # （主题、榜单 / 搜索偏好）每次开窗都是新的。固定到用户目录才留得住。
        private_mode=False,
        storage_path=str(paths.WEBVIEW_DIR),
        func=lambda: glass.apply(window, window_cfg),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:      # 开窗前的任何意外，都不该只给用户留下一片安静
        _alert(f"启动失败：{exc}")
        raise
