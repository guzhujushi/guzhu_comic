"""
桌面集成：窗口位置记忆、系统通知、托盘图标、开机自启、全局快捷键、打开目录。

**零新增依赖**是有意的：这一版 exe 已经发出去了，再加一个包（比如 pystray）就得重打包 ——
所以托盘与通知走 pywebview 自带的 pythonnet（Windows 后端的 WinForms 本来就在包里），
开机自启走 stdlib 的 winreg，全局快捷键走 ctypes。

这里所有东西都是"最好有"：任何一步失败只打一行日志，**绝不让开窗挂在这上面**；
非 Windows 一律静默降级（返回值一律"没那么回事"，不抛异常）。
"""
import ctypes
import ctypes.wintypes as wintypes
import logging
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Callable

from backend import paths
from backend.config import load_config, save_config

IS_WINDOWS = sys.platform == "win32"

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "GuzhuComic"

# 托盘 / 通知那份 NotifyIcon 的保管处（必须留个引用，不然会被 GC 掉、图标当场消失）
_tray: dict[str, Any] = {"icon": None, "form": None, "tray_on": False}
_hotkey: dict[str, Any] = {"thread": None, "ok": False, "hidden": False}


def log(message: str) -> None:
    """桌面集成的问题都走这儿：平时没人看，出问题时它就在日志里"""
    logging.getLogger("app").info("[desktop] %s", message)


# ---------------- 打开东西 ----------------

def open_url(url: str) -> bool:
    """用系统默认浏览器打开一个 http(s) 地址（"关于"页的链接、更新说明都走它）"""
    text = str(url or "").strip()
    if not text.startswith(("http://", "https://")):
        raise ValueError("只能打开 http / https 地址")
    try:
        webbrowser.open(text)
        return True
    except Exception as e:          # noqa: BLE001 —— 打不开浏览器不该惊动界面
        log(f"打开链接失败（{text}）：{e}")
        return False


def folder_path(kind: str) -> Path:
    """`logs` / `downloads` / `data` / `cache` / `web` 这几个目录的实际位置"""
    cfg = load_config()
    kind = str(kind or "").strip().lower()
    if kind == "logs":
        return paths.APP_DIR / "logs"
    if kind == "downloads":
        download = cfg.get("download") or {}
        return paths.resolve_download_dir(download.get("dir"))
    if kind == "data":
        return paths.DATA_DIR
    if kind == "cache":
        return paths.CACHE_DIR
    if kind == "web":
        return paths.WEB_DIR
    if kind == "app":
        return paths.APP_DIR
    raise ValueError("不认识的目录：" + kind)


def open_folder(kind: str) -> dict:
    """
    在资源管理器里把这个目录打开（数据在哪、日志在哪，一句话说不清时就点一下）。
    只认上面那几个 kind —— 不收任意路径，省得这条接口成了"随便打开本机哪都行"。
    """
    path = folder_path(kind)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"目录建不出来（{path}）：{e}") from e
    if not IS_WINDOWS:
        return {"opened": False, "path": str(path), "reason": "只有 Windows 上支持打开目录"}
    try:
        # 用 explorer 而不是 os.startfile：startfile 对目录的默认动作有时被第三方接管成"用某个程序打开"
        subprocess.Popen(["explorer", str(path)])
        return {"opened": True, "path": str(path)}
    except Exception as e:          # noqa: BLE001
        log(f"打开目录失败（{path}）：{e}")
        return {"opened": False, "path": str(path), "reason": str(e)}


# ---------------- 开机自启（HKCU，不要管理员） ----------------

def _autostart_cmd() -> str:
    """
    写进启动项的那条命令。

    冻结态就是自己的 exe；源码态指向 `pythonw main.py`（只是让开发机上也能试，
    正常情况下别开 —— 那样开机后跑的是开发目录）。
    """
    if paths.is_frozen():
        return f'"{sys.executable}"'
    main_py = paths.bundle_dir() / "main.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    runner = pythonw if pythonw.is_file() else Path(sys.executable)
    return f'"{runner}" "{main_py}"'


def autostart_get() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_NAME)
        return bool(str(value).strip())
    except FileNotFoundError:
        return False
    except OSError as e:
        log(f"读开机自启失败：{e}")
        return False


def autostart_set(enabled: bool) -> bool:
    """返回"设置之后是不是开着"；失败只在日志里说一声"""
    if not IS_WINDOWS:
        return False
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, _autostart_cmd())
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
        log(f"开机自启：{'已开' if enabled else '已关'}")
    except OSError as e:
        log(f"写开机自启失败：{e}")
    return autostart_get()


def sync_autostart(cfg: dict) -> None:
    """开窗时对一遍账：配置说要自启而启动项里没有（或反过来），就补上 / 去掉。

    为什么放在开窗时做：这样它跟 `desktop.autostart` 这个配置项永远是一致的，
    不用在设置页保存那条路上再走一遍注册表。
    """
    if not IS_WINDOWS:
        return
    want = bool((cfg.get("desktop") or {}).get("autostart"))
    if want != autostart_get():
        autostart_set(want)


# ---------------- 窗口位置 / 大小记忆 ----------------

def _virtual_screen() -> tuple[int, int, int, int]:
    """整个虚拟桌面的 (左, 上, 宽, 高)（多显示器时是并集）"""
    try:
        u = ctypes.windll.user32
        return (u.GetSystemMetrics(76), u.GetSystemMetrics(77),
                u.GetSystemMetrics(78), u.GetSystemMetrics(79))
    except Exception:               # noqa: BLE001
        return (0, 0, 1920, 1080)


def geometry_kwargs(cfg: dict) -> dict:
    """
    开窗时该用多大的窗口、摆哪儿。

    记忆里的位置落在屏幕外（拔了显示器 / 换了分辨率）就只沿用大小、不摆过去 ——
    否则窗口会开在看得见的地方之外，用户会以为"打开没反应"。
    """
    win = cfg.get("window") or {}
    try:
        width = max(320, int(win.get("width") or 1200))
        height = max(240, int(win.get("height") or 800))
    except (TypeError, ValueError):
        width, height = 1200, 800
    out: dict[str, int] = {"width": width, "height": height}
    if not win.get("remember_geometry"):
        return out

    geo = win.get("last_geometry")
    if not isinstance(geo, (list, tuple)) or len(geo) != 4:
        return out
    try:
        x, y, saved_w, saved_h = (int(v) for v in geo)
    except (TypeError, ValueError):
        return out

    mins = win.get("min_size") or [800, 600]
    try:
        min_w, min_h = int(mins[0]), int(mins[1])
    except (TypeError, ValueError, IndexError):
        min_w, min_h = 800, 600
    width = max(min_w, min(saved_w, 20000))
    height = max(min_h, min(saved_h, 20000))
    out.update({"width": width, "height": height})

    vx, vy, vw, vh = _virtual_screen()
    if vx - 80 <= x <= vx + vw - 160 and vy - 20 <= y <= vy + vh - 80:
        out.update({"x": x, "y": y})
    else:
        log(f"记住的位置 ({x}, {y}) 已经在屏幕外了，这次只沿用大小")
    return out


def _window_rect(window) -> tuple[int, int, int, int] | None:
    """当前窗口的 (x, y, 宽, 高)；最大化时说 None（那尺寸不是用户挑的，别记）"""
    form = _form(window)
    if form is not None:
        try:
            if str(form.WindowState).lower().startswith("maxim"):
                return None
        except Exception:           # noqa: BLE001
            pass
    try:
        return (int(window.x), int(window.y), int(window.width), int(window.height))
    except Exception as e:          # noqa: BLE001
        log(f"读窗口位置失败：{e}")
        return None


def watch_geometry(window, cfg: dict) -> None:
    """挂上关窗时那一笔：下次开窗照着摆"""
    if not (cfg.get("window") or {}).get("remember_geometry"):
        return

    def on_closing(*_args, **_kwargs):
        rect = _window_rect(window)
        if rect is None or any(v <= 0 for v in rect[2:]):
            return
        try:
            if [int(v) for v in (cfg.get("window") or {}).get("last_geometry") or []] == list(rect):
                return                  # 位置大小没变：别白写一次配置文件
        except (TypeError, ValueError):
            pass
        try:
            fresh = load_config()          # 现读一次：设置页可能刚改过别的项，别把它覆盖回去
            fresh.setdefault("window", {})["last_geometry"] = list(rect)
            save_config(fresh)
            log(f"记下窗口位置：{rect}")
        except Exception as e:          # noqa: BLE001 —— 记不住位置而已，不打扰用户
            log(f"窗口位置没记住：{e}")

    try:
        window.events.closing += on_closing
    except Exception as e:              # noqa: BLE001
        log(f"挂关窗钩子失败：{e}")


# ---------------- 托盘 / 通知 / 快捷键 ----------------

def _form(window):
    """拿到 pywebview 那个 WinForms Form（玻璃、托盘、快捷键都靠它回 UI 线程）"""
    try:
        from webview.platforms import winforms
        return winforms.BrowserView.instances.get(getattr(window, "uid", "master"))
    except Exception:               # noqa: BLE001
        return None


def _ui(form, work: Callable[[], None]) -> None:
    """把一件事丢回 UI 线程做；丢不进去就直接做（拿不到 form 的时候）"""
    if form is None:
        work()
        return
    try:
        from System import Action
        form.BeginInvoke(Action(work))
    except Exception:               # noqa: BLE001
        work()


def _tray_icon_data():
    """托盘图标：优先从 exe 里抠（打包态最省事），抠不出来就拿前端那张 PNG 现做一个"""
    if IS_WINDOWS:
        try:
            from System.Drawing import Icon
            icon = Icon.ExtractAssociatedIcon(sys.executable)
            if icon is not None:
                return icon
        except Exception:           # noqa: BLE001
            pass
    candidates = (
        paths.WEB_DIR / "apple-touch-icon.png",
        paths.dist_dir() / "apple-touch-icon.png",
        paths.dist_dir() / "apple-touch-icon-256.png",
        paths.bundle_dir() / "frontend" / "public" / "apple-touch-icon.png",
    )
    for png in candidates:
        if not png.is_file():
            continue
        try:
            from System.Drawing import Bitmap, Icon
            bitmap = Bitmap(str(png))
            return Icon.FromHandle(bitmap.GetHicon())
        except Exception:           # noqa: BLE001
            continue
    return None


def _mk_notify_icon(window, want_tray: bool) -> None:
    """
    建那个 NotifyIcon（托盘图标 + 系统通知都要用它）。

    必须在 UI 线程上建（WinForms 的控件都这样），所以整段用 `_ui` 包着 ——
    `webview.start(func=...)` 那个回调是在**别的线程**里跑的，直接建会时灵时不灵。
    """
    form = _form(window)

    def build():
        try:
            import clr                       # noqa: F401 —— pythonnet 得先导入才认得 System.*
            from System.Windows.Forms import (ContextMenuStrip, NotifyIcon, ToolStripMenuItem,
                                              ToolStripSeparator)
            from System.Drawing import Icon
        except Exception as e:               # noqa: BLE001
            log(f"托盘起不来（没有 WinForms / pythonnet）：{e}")
            return

        icon_data = _tray_icon_data()
        ball = NotifyIcon()
        ball.Text = "孤竹漫画"
        if icon_data is not None:
            ball.Icon = icon_data

        def show_window(*_a):
            _hotkey["hidden"] = False
            for fn in (window.show, window.restore):
                try:
                    fn()
                except Exception:            # noqa: BLE001
                    pass

        def open_data(*_a):
            try:
                subprocess.Popen(["explorer", str(paths.APP_DIR)])
            except Exception as e:           # noqa: BLE001
                log(f"托盘打不开数据目录：{e}")

        def quit_app(*_a):
            try:
                ball.Visible = False
                window.destroy()
            except Exception as e:           # noqa: BLE001
                log(f"托盘退出失败：{e}")

        menu = ContextMenuStrip()
        for text, handler in (("显示主窗口", show_window), ("打开数据目录", open_data)):
            item = ToolStripMenuItem(text)
            item.Click += handler
            menu.Items.Add(item)
        menu.Items.Add(ToolStripSeparator())
        quit_item = ToolStripMenuItem("退出")
        quit_item.Click += quit_app
        menu.Items.Add(quit_item)

        ball.ContextMenuStrip = menu
        ball.DoubleClick += show_window
        ball.Visible = bool(want_tray)
        _tray.update({"icon": ball, "form": form, "tray_on": bool(want_tray)})
        log(f"托盘就绪（图标{'开' if want_tray else '关'}）")

    _ui(form, build)


def notify(title: str, message: str, cfg: dict | None = None, force: bool = False) -> bool:
    """弹一条 Windows 通知；托盘那份 NotifyIcon 没建起来就什么都不做"""
    cfg = cfg if isinstance(cfg, dict) else load_config()
    if not force and not bool((cfg.get("desktop") or {}).get("notify", True)):
        return False
    ball = _tray.get("icon")
    if ball is None:
        return False
    form = _tray.get("form")

    def show():
        try:
            from System.Windows.Forms import ToolTipIcon
            ball.ShowBalloonTip(6000, str(title), str(message), ToolTipIcon.Info)
        except Exception as e:               # noqa: BLE001
            log(f"通知没弹出来：{e}")

    _ui(form, show)
    return True


# 全局快捷键：RegisterHotKey(NULL, ...) 会把 WM_HOTKEY 投到**调用它的那个线程**的消息队列，
# 所以自己起一个线程注册 + GetMessage 泵着 —— 不用建窗口类，也不用碰 UI 线程。
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x0008, 0x4000
_KEY_NAMES = {
    "SPACE": 0x20, "ENTER": 0x0D, "TAB": 0x09, "ESC": 0x1B, "ESCAPE": 0x1B,
    "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}


def parse_hotkey(text: str) -> tuple[int, int] | None:
    """`Ctrl+Alt+G` → (modifiers, vk)；认不出来返回 None"""
    parts = [p.strip().upper() for p in str(text or "").replace(" ", "").split("+") if p.strip()]
    if len(parts) < 2:
        return None
    mods = 0
    key = None
    for part in parts:
        if part in ("CTRL", "CONTROL"):
            mods |= MOD_CONTROL
        elif part == "ALT":
            mods |= MOD_ALT
        elif part == "SHIFT":
            mods |= MOD_SHIFT
        elif part in ("WIN", "SUPER", "META"):
            mods |= MOD_WIN
        elif len(part) == 1 and part.isalnum():
            key = ord(part)
        elif part in _KEY_NAMES:
            key = _KEY_NAMES[part]
        elif part.startswith("F") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            key = 0x70 + int(part[1:]) - 1
        else:
            return None
    if key is None or mods == 0:
        return None
    return mods | MOD_NOREPEAT, key


def _toggle_window(window) -> None:
    """快捷键那一下：窗口在前台就收起来，不在就拉出来"""
    hidden = bool(_hotkey.get("hidden"))
    try:
        if hidden:
            window.show()
            window.restore()
        else:
            window.hide()
        _hotkey["hidden"] = not hidden
    except Exception as e:               # noqa: BLE001
        log(f"切换窗口失败：{e}")


def _register_hotkeys(window, spec: str) -> None:
    parsed = parse_hotkey(spec)
    if parsed is None:
        log(f"快捷键认不出来，跳过：{spec!r}（形如 Ctrl+Alt+G）")
        return
    mods, vk = parsed

    def loop():
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, 1, mods, vk):
            log(f"快捷键被别的程序占着了，没注册上：{spec}")
            return
        _hotkey["ok"] = True
        log(f"全局快捷键已注册：{spec}")
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == 1:
                    _toggle_window(window)
        finally:
            user32.UnregisterHotKey(None, 1)

    thread = threading.Thread(target=loop, daemon=True, name="hotkeys")
    _hotkey["thread"] = thread
    thread.start()


def setup(window, cfg: dict) -> None:
    """
    在 `webview.start(func=...)` 那个线程里调一次：托盘 + 通知 + 全局快捷键。

    窗口位置记忆不在这儿 —— 那个在开窗前就要用上（`geometry_kwargs`），
    关窗时再记一笔（`watch_geometry`）。
    """
    desktop = cfg.get("desktop") or {}
    try:
        if bool(desktop.get("tray", True)) or bool(desktop.get("notify", True)):
            _mk_notify_icon(window, bool(desktop.get("tray", True)))
    except Exception as e:               # noqa: BLE001
        log(f"托盘初始化失败：{e}")
    try:
        if bool(desktop.get("hotkeys")):
            _register_hotkeys(window, str(desktop.get("hotkey_toggle") or "Ctrl+Alt+G"))
    except Exception as e:               # noqa: BLE001
        log(f"全局快捷键初始化失败：{e}")


def desktop_state(cfg: dict | None = None) -> dict:
    """设置页看一眼实际状态（配置只是"想要什么"，这里是"实际怎么样"）"""
    cfg = cfg if isinstance(cfg, dict) else load_config()
    desktop = cfg.get("desktop") or {}
    return {
        "platform": sys.platform,
        "notify": bool(desktop.get("notify", True)),
        "tray": bool(desktop.get("tray", True)),
        "tray_live": _tray.get("icon") is not None,
        "autostart": autostart_get(),
        "hotkeys": bool(desktop.get("hotkeys")),
        "hotkeys_live": bool(_hotkey.get("ok")),
        "hotkey_toggle": str(desktop.get("hotkey_toggle") or "Ctrl+Alt+G"),
    }
