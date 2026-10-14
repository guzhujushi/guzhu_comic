# -*- coding: utf-8 -*-
r"""跨平台兜底的用例：非 Windows 上，三个平台模块必须"放行 / 什么都不做"，一步都不许碰 Win32。

跑法：.venv\Scripts\python.exe tmp\_check_platform_failopen.py

本机是 Windows，所以这里把 sys.platform 临时改成 darwin 来走那条分支 —— 能验的只有"分支被走到了
且是 fail-open"（真正的 mac / 安卓行为仍然没验过，见 tmp/打包分发设计.md §9）。
"""
import ctypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import glass, paths, single_instance, webview2  # noqa: E402

FAILS: list = []


def expect(cond: bool, msg: str) -> None:
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


def main() -> int:
    real_platform = sys.platform

    # 数据 / 配置路径：跨平台的唯一入口，不该出现盘符或反斜杠硬编码
    expect(paths.APP_DIR == Path.home() / ".jmreader",
           "数据目录在 home 下（%s）" % (paths.APP_DIR,))
    expect(paths.resolve_download_dir("~/x").is_absolute(),
           "下载目录能解析成绝对路径（~ 与相对路径都认）")

    def must_not_be_called(*_a, **_kw):
        raise AssertionError("非 Windows 上不该去碰注册表")

    real_read_pv = webview2._read_pv
    webview2._read_pv = must_not_be_called
    try:
        sys.platform = "darwin"
        expect(glass.enabled({"glass": "acrylic"}) is False,
               "非 Windows：毛玻璃整条路跳过（不碰 DWM）")
        expect(single_instance.acquire() is True,
               "非 Windows：单实例放行（不建互斥体）")
        expect(single_instance._handle is None, "非 Windows：真的没去建互斥体句柄")
        expect(single_instance.focus_existing("随便什么标题") is False,
               "非 Windows：不去抢前台，返回 False（不抛异常）")
        expect(webview2.installed() is True,
               "非 Windows：WebView2 检查直接放行（winreg 在 mac 上根本不存在）")
    finally:
        sys.platform = real_platform
        webview2._read_pv = real_read_pv

    # 弹窗：非 Windows 没有 ctypes.windll，_alert 只能退化成 print —— 但绝不能因此再炸一次
    from main import _alert  # noqa: E402  （import main 只是导入，不开窗）

    saved_windll = getattr(ctypes, "windll", None)
    try:
        if saved_windll is not None:
            del ctypes.windll
        _alert("测试：非 Windows 上弹不出窗")
        expect(True, "没有 ctypes.windll 时 _alert 不炸（退化成一个 print）")
    except Exception as e:
        expect(False, "没有 ctypes.windll 时 _alert 抛了 %r" % (e,))
    finally:
        if saved_windll is not None:
            ctypes.windll = saved_windll

    print()
    print("结果:", FAILS if FAILS else "全部通过")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
