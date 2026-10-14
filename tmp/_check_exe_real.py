# -*- coding: utf-8 -*-
r"""正式包（未改动的 build_out 产物）首启验收：能不能双击就用。

跑法：.venv/Scripts/python.exe tmp/_check_exe_real.py
"""
import ctypes
import ctypes.wintypes as wt
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("D:/guzhu_comic")
EXE = ROOT / "build_out" / "GuzhuComic" / "GuzhuComic.exe"
CFG = Path.home() / ".jmreader" / "config.yaml"
PORT = 47753


def titles_by_pid():
    out = {}
    buf = ctypes.create_unicode_buffer(512)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        if buf.value:
            pid = wt.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.setdefault(pid.value, []).append(buf.value)
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    return out


def main():
    ok = True
    if not EXE.exists():
        print("FAIL  没有 exe：" + str(EXE), flush=True)
        return False
    # 真首启：清掉上一轮留下的用户配置与 WebView2 数据（否则同源 HTTP 缓存 / localStorage
    # 会把上一轮的状态带进来 —— 探针副本与正式包是同一个 origin、同一个 webview 目录）
    if CFG.exists():
        CFG.unlink()
        print("[setup] 清掉旧的 config.yaml", flush=True)
    wv_dir = Path.home() / ".jmreader" / "webview"
    if wv_dir.exists():
        shutil.rmtree(wv_dir, ignore_errors=True)
        print("[setup] 清掉旧的 WebView2 用户数据", flush=True)

    print("[setup] 起包：" + str(EXE), flush=True)
    proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    time.sleep(10)

    if proc.poll() is not None:
        print("FAIL  exe 10 秒内就退了，退出码 " + str(proc.returncode), flush=True)
        return False
    print("[check] 进程还活着 pid=" + str(proc.pid), flush=True)

    wins = [w for w in titles_by_pid().get(proc.pid, [])]
    print("[check] 窗口标题=" + json.dumps(wins, ensure_ascii=False), flush=True)
    if "Guzhu Comic" not in wins:
        print("FAIL  没看到标题为 Guzhu Comic 的窗口", flush=True)
        ok = False

    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/index.html" % PORT, timeout=5) as r:
            body = r.read().decode("utf-8", "replace")
        print("[check] :%d/index.html -> %d 字节" % (PORT, len(body)), flush=True)
        if "PROBE" in body:
            print("FAIL  居然还带着探针（这份不该是副本！）", flush=True)
            ok = False
    except Exception as e:
        print("FAIL  静态服务连不上：%r" % (e,), flush=True)
        ok = False

    if not CFG.exists():
        print("FAIL  首启没把默认配置写到 " + str(CFG), flush=True)
        ok = False
    else:
        text = CFG.read_text(encoding="utf-8")
        print("[check] 首启写出的 " + str(CFG), flush=True)
        for line in text.splitlines():
            if any(k in line for k in ("title:", "use_dev_server:", "debug:", "port:")):
                print("        " + line.strip(), flush=True)
        if "PROBE" in text:
            print("FAIL  配置里带着探针字串", flush=True)
            ok = False

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True)
    print("\n=> " + ("全部通过" if ok else "有问题，见上面的 FAIL"), flush=True)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
