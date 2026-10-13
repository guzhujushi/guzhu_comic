"""Windows 上的窗口毛玻璃。

要出真模糊得凑齐三件事：WebView2 的底要是透明的（由 pywebview 的 transparent=True
负责，它在建窗时就在 UI 线程上设好了）、窗口整体压成半透明（Form.Opacity）、
再让 DWM 在窗口后面画一层亚克力。页面里那堆 backdrop-filter 只是叠在上面，
真把桌面内容模糊掉的是系统。

动手的时机很要紧：pywebview 的透明窗口是先 Show() 再 Hide()、等 WebView2 开始
导航才真正显示，抢在这个缝隙里改窗口属性会把窗口按在隐藏状态再也出不来。所以这里
一直等到页面加载完、窗口真的可见了，再把改动丢回 UI 线程执行；要是等不到窗口，
就什么都不做。

SYSTEMBACKDROP_TYPE 要 Win11 22H2 起才有：老系统上这一脚会被系统拒掉，那就连
透明度也不压，窗口退化成普通不透明窗口，总比透着一层没模糊的桌面强。
"""
import ctypes
import sys
import time

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38

BACKDROPS = {'none': 1, 'mica': 2, 'acrylic': 3, 'tabbed': 4}


class _MARGINS(ctypes.Structure):
    _fields_ = [
        ('left', ctypes.c_int),
        ('right', ctypes.c_int),
        ('top', ctypes.c_int),
        ('bottom', ctypes.c_int),
    ]


def enabled(cfg: dict) -> bool:
    """非 Windows，或者配置里写 none，就完全不动窗口"""
    if sys.platform != 'win32':
        return False
    kind = str(cfg.get('glass', 'none')).lower()
    return kind in BACKDROPS and kind != 'none'


def _top_level_hwnd(title: str) -> int:
    user32 = ctypes.windll.user32
    for _ in range(40):
        hwnd = user32.FindWindowW(None, title)
        if hwnd and user32.IsWindowVisible(hwnd):
            return hwnd
        time.sleep(0.25)
    return 0


def _dwm(hwnd: int, kind: int) -> bool:
    """铺亚克力底；返回系统认不认这一步"""
    api = ctypes.windll.dwmapi
    dark = ctypes.c_int(1)
    api.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), 4)
    margins = _MARGINS(-1, -1, -1, -1)
    api.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
    backdrop = ctypes.c_int(kind)
    return api.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), 4) == 0


def apply(window, cfg: dict) -> None:
    """在 webview.start(func=...) 的线程里调"""
    if not enabled(cfg):
        return

    try:
        window.events.loaded.wait(30)
    except Exception:
        pass

    hwnd = _top_level_hwnd(window.title)
    if not hwnd:
        return

    opacity = min(1.0, max(0.35, float(cfg.get('glass_opacity') or 0.92)))
    kind = BACKDROPS[str(cfg['glass']).lower()]

    try:
        from webview.platforms import winforms
        form = winforms.BrowserView.instances.get(getattr(window, 'uid', 'master'))
    except Exception:
        form = None

    def work():
        if not _dwm(hwnd, kind):
            return
        if form is not None:
            try:
                form.Opacity = opacity
            except Exception:
                pass

    if form is None:
        work()
        return
    try:
        from System import Action
        form.BeginInvoke(Action(work))   # Form 只能在 UI 线程上改
    except Exception:
        work()