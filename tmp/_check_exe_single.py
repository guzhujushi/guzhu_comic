# -*- coding: utf-8 -*-
r"""真 exe 的单实例行为验收：开第二个时，它应当弹一句提示然后自己退出，第一个不受影响。

跑法：.venv/Scripts/python.exe tmp/_check_exe_single.py
"""
import ctypes
import ctypes.wintypes as wt
import json
import subprocess
import sys
import time
from pathlib import Path

EXE = Path("D:/guzhu_comic/build_out/GuzhuComic/GuzhuComic.exe")
WIN_TITLE = "Guzhu Comic"
DIALOG_TITLE = "孤竹漫画"

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
user32.PostMessageW.restype = ctypes.c_bool
user32.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
WM_CLOSE = 0x0010

FAILS = []


def expect(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


def windows_by_pid():
    out = {}
    buf = ctypes.create_unicode_buffer(512)
    cls = ctypes.create_unicode_buffer(256)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        user32.GetWindowTextW(hwnd, buf, 512)
        if buf.value:
            user32.GetClassNameW(hwnd, cls, 256)
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.setdefault(pid.value, []).append((buf.value, cls.value))
        return True

    user32.EnumWindows(cb, 0)
    return out


def wait_window(pid, title, timeout=25.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for w, cls in windows_by_pid().get(pid, []):
            if w == title:
                return True
        time.sleep(0.5)
    return False


def main():
    if not EXE.exists():
        print("FAIL  没有 exe：" + str(EXE), flush=True)
        return 1

    first = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    expect(wait_window(first.pid, WIN_TITLE, 30), "第一个实例起来了，窗口标题 %r" % WIN_TITLE)

    second = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    time.sleep(3.0)

    dlg = user32.FindWindowW(None, DIALOG_TITLE)
    wins2 = windows_by_pid().get(second.pid, [])
    print("[info] 第二个实例的顶层窗口：" + json.dumps(wins2, ensure_ascii=False), flush=True)
    expect(bool(dlg), "第二个实例弹出了提示框（标题 %r）" % DIALOG_TITLE)
    if dlg:
        user32.PostMessageW(dlg, WM_CLOSE, None, None)

    deadline = time.time() + 10
    while time.time() < deadline and second.poll() is None:
        time.sleep(0.3)
    expect(second.poll() is not None, "第二个实例自己退出了（退出码 %r）" % (second.returncode,))
    expect(second.returncode in (0, None) and second.poll() == 0, "第二个实例退出码 0（实际 %r）" % (second.returncode,))

    alive = first.poll() is None
    expect(alive, "第一个实例还在跑")
    expect(wait_window(first.pid, WIN_TITLE, 3), "第一个实例的窗口还在（没被第二个顶掉）")

    if first.poll() is None:
        subprocess.run(["taskkill", "/PID", str(first.pid), "/T", "/F"], capture_output=True, text=True)
    time.sleep(1)

    print()
    print("结果:", FAILS if FAILS else "全部通过", flush=True)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
