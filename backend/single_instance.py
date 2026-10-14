r"""
单实例：同一个登录会话里只允许开一个窗口。

用命名互斥体（kernel mutex），不用"探测端口有没有人应"—— 后者会被用户改端口、或者别的程序占端口
搞乱，而且有竞态。互斥体是原子的：第二个进程创建时立刻就知道"已经有了"。

第二个实例的做法：提示一句 + 尽量把已经在跑的那个窗口拉到前台，然后退出。

名字不带 `Global\` 前缀 = 按登录会话隔离（同一台机器多用户登录各自一份，正合适）。

拿不准（非 Windows / 建不出来）一律返回 True，也就是放行 —— 别让单实例把能跑的机器拦在门外。

平台差异集中在 glass.py / webview2.py / single_instance.py；将来上 mac / Android 时一起挪进
backend/platform/ 门面。
"""
import ctypes
import sys

_MUTEX_NAME = "GuzhuComic.SingleInstance"
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9

# 句柄一直留着：进程活着它就活着，进程一退系统自动回收（别让局部变量提前把它回收掉）
_handle = None


def acquire() -> bool:
    """True = 本进程拿到了这把锁（第一个实例）；False = 已经有一个在跑了"""
    global _handle
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
        _handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not _handle:
            return True         # 建不出来（权限等）：别拦着人开窗
        return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS
    except Exception as e:
        print(f"[single] 单实例锁没建起来，先放行: {e}", flush=True)
        return True


def focus_existing(title: str) -> bool:
    """把已经在跑的那个窗口拉到前台；找不到就返回 False（这不是错误）"""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False
