# -*- coding: utf-8 -*-
r"""WebView2 检测的用例：装了 / 没装 / 查不了（要 fail-open）。

跑法：.venv\Scripts\python.exe tmp\_check_webview2.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import webview2  # noqa: E402

FAILS: list = []


def expect(cond: bool, msg: str) -> None:
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


def main() -> int:
    real = webview2._read_pv
    try:
        pv = real()
    except Exception as e:
        pv = "<读注册表出错 %r>" % (e,)

    expect(webview2.installed() is True, "本机应当判定为已装（pv=%r）" % (pv,))

    webview2._read_pv = lambda: None
    expect(webview2.installed() is False, "三个位置都没有这个键 -> 没装")
    webview2._read_pv = lambda: ""
    expect(webview2.installed() is False, "pv 是空串 -> 没装")
    webview2._read_pv = lambda: "0.0.0.0"
    expect(webview2.installed() is False, "pv 是 0.0.0.0 -> 没装")
    webview2._read_pv = lambda: "155.0.4283.45"
    expect(webview2.installed() is True, "正常版本号 -> 已装")

    def boom():
        raise PermissionError(5, "access denied")

    webview2._read_pv = boom
    expect(webview2.installed() is True, "注册表读不了 -> fail-open（放行，别拦着能跑的机器）")
    webview2._read_pv = real

    print()
    print("结果:", FAILS if FAILS else "全部通过")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
