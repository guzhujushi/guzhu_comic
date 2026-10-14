# -*- coding: utf-8 -*-
r"""强制"没装 WebView2"跑一遍开窗流程：提示框该不该出来、文案对不对。

走的是 main.py 里那段真代码（源态跑，跟 exe 里同一份）；只把 installed() 换成固定 False，
并把"打开下载页"换成记账，免得测试时真弹出浏览器。

跑法：.venv/Scripts/python.exe tmp/_check_webview2_gate.py
"""
import ctypes
import ctypes.wintypes as wt
import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import webview2  # noqa: E402
import main as app  # noqa: E402

FAILS = []
DIALOG_TITLE = "孤竹漫画"
WM_CLOSE = 0x0010

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
user32.PostMessageW.restype = ctypes.c_bool
user32.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)


def expect(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


def dialog_text(hwnd):
    """把弹窗里所有子控件的文字拼起来（正文就在 static 控件里）"""
    out = []
    buf = ctypes.create_unicode_buffer(2048)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(child, _):
        user32.GetWindowTextW(child, buf, 2048)
        if buf.value.strip():
            out.append(buf.value.strip())
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return " | ".join(out)


def main():
    opened = []
    real_open = webbrowser.open
    webbrowser.open = lambda url, *a, **kw: opened.append(url) or True
    webview2.installed = lambda: False       # 假装这台机器没装

    thread = threading.Thread(target=app.main, daemon=True)
    thread.start()

    hwnd = None
    deadline = time.time() + 15
    while time.time() < deadline:
        hwnd = user32.FindWindowW(None, DIALOG_TITLE)
        if hwnd:
            break
        time.sleep(0.3)

    expect(bool(hwnd), "弹出了提示框（标题 %r）" % DIALOG_TITLE)
    if hwnd:
        text = dialog_text(hwnd)
        print("[info] 弹窗正文：" + text, flush=True)
        expect("WebView2" in text, "正文里说清了缺的是 WebView2")
        expect("装好" in text or "重新双击" in text, "正文里给了「接下来怎么办」")
        user32.PostMessageW(hwnd, WM_CLOSE, None, None)

    thread.join(timeout=10)
    expect(not thread.is_alive(), "关掉提示框后流程正常结束（没有卡住）")
    expect(opened and opened[0].startswith("https://go.microsoft.com/"), "自动打开了微软下载页（记录：%r）" % (opened,))
    expect(not any(w == "Guzhu Comic" for w in _titles()), "没有开窗（缺运行时时不该给一个白窗口）")

    webbrowser.open = real_open
    print()
    print("结果:", FAILS if FAILS else "全部通过", flush=True)
    return 0 if not FAILS else 1


def _titles():
    out = []
    buf = ctypes.create_unicode_buffer(512)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        user32.GetWindowTextW(hwnd, buf, 512)
        if buf.value:
            out.append(buf.value)
        return True

    user32.EnumWindows(cb, 0)
    return out


if __name__ == "__main__":
    sys.exit(main())
