"""
WebView2 Runtime 检测（Windows 专用）。

Win11 与 Win10 1803+ 基本自带（跟着 Edge 一起发），但精简过的系统、老一些的 Win10、或者被清理
工具删过的机器上确实可能没有 —— 那时 pywebview 根本起不来，用户看到的只是一个白窗口，什么提示
都没有。所以开窗之前先查一眼。

判定用微软自己那套：EdgeUpdate 客户端键（{F3017226-…}）的 `pv` 值。三个位置都看（机器级 32 位
视图 / 机器级 64 位视图 / 用户级），任何一个有非空 pv 就算装了。

查不到一律**当成装了**（fail-open）：非 Windows、权限不够、注册表读出错 —— 宁可让 pywebview 自己
报错，也不要把本来能跑的机器拦在门外。

平台差异集中在 glass.py / webview2.py / single_instance.py 这三个模块里；将来上 mac / Android 时
它们一起挪进 backend/platform/ 门面，业务代码一行不用动。
"""
import sys
from typing import Optional

# 微软官方给的 WebView2 Runtime 客户端 ID（就是 EdgeUpdate\Clients 下的那个子键名）
CLIENT_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_SUBKEY = "Microsoft\\EdgeUpdate\\Clients\\" + CLIENT_ID

# Evergreen 引导装包（很小，装完运行时自动更新），微软短链
DOWNLOAD_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def _read_pv() -> Optional[str]:
    """
    去注册表里找 WebView2 的 pv（版本号）。

    返回 None = 三个位置都没有这个键（= 没装）；返回字符串 = 找到了（可能是空串，那按没装算）。
    读出错（权限等）直接抛 OSError，交给调用方决定怎么办。
    """
    import winreg

    roots = (
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + _SUBKEY),
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + _SUBKEY),
        (winreg.HKEY_CURRENT_USER, "SOFTWARE\\" + _SUBKEY),
    )
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as key:
                return str(winreg.QueryValueEx(key, "pv")[0]).strip()
        except FileNotFoundError:
            continue        # 这个位置没有，看下一个
    return None


def installed() -> bool:
    """装了 WebView2 Runtime 吗（拿不准就返回 True）"""
    if sys.platform != "win32":
        return True
    try:
        pv = _read_pv()
    except Exception as e:      # 权限 / 注册表损坏 / winreg 用不了：别下结论
        print(f"[webview2] 查不到运行时版本，先按装了处理: {e}", flush=True)
        return True
    if pv is None:
        return False
    return pv not in ("", "0.0.0.0")
