# -*- coding: utf-8 -*-
"""
安卓壳上的 token 闸门：**不是本 app 的进程**（adb shell，uid 2000）去读 127.0.0.1:47753，
没有 token 应当被拒（T8 那个洞），带上 token 才放行。

前提：壳正在跑（`adb shell am start -n cn.guzhujushi.comic/cn.guzhujushi.comic.MainActivity`），
token 从 logcat 里那条页面地址（`?t=`）里取。没设备 / 壳没跑就 SKIP（不算失败）。
"""
import os
import pathlib
import re
import subprocess
import sys

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")


def run(args: list[str], timeout: int = 60) -> str:
    r = subprocess.run([ADB] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def probe(path: str) -> str:
    """在设备上发一个最原始的 HTTP 请求（toybox nc，不经过任何 app）"""
    cmd = ('printf "GET %s HTTP/1.0\\r\\nHost: 127.0.0.1\\r\\n\\r\\n" | toybox nc 127.0.0.1 47753'
           % path)
    out = run(["shell", cmd]).strip()
    return out.splitlines()[0].strip() if out else "（没有回应）"


devices = [l for l in run(["devices"]).splitlines() if "\tdevice" in l]
if not devices:
    print("SKIP：没有连着设备 / 模拟器")
    sys.exit(0)

state = run(["shell", "getprop", "ro.dalvik.vm.native.bridge"]).strip()
# `pidof` 打的是 PID（不是包名），所以判"有没有数字"而不是判字符串
running = bool(re.search(r"\d", run(["shell", "pidof", "cn.guzhujushi.comic"])))
if not running:
    print("SKIP：cn.guzhujushi.comic 没在跑（先起壳再看这个）")
    sys.exit(0)

log = run(["logcat", "-d", "-s", "GuzhuShell:*"])
m = re.search(r"\?t=([A-Za-z0-9_\-]+)", log)
if not m:
    print("FAIL：logcat 里找不到带 ?t= 的页面地址")
    sys.exit(1)
token = m.group(1)
print("设备：%s | native.bridge=%s | token 前 8 位 %s…" % (devices[0].split()[0], state, token[:8]))

fails = []
no_token = probe("/images/anything/1.webp")
ok1 = "403" in no_token
print(("  PASS  " if ok1 else "  FAIL  ") + "另一个进程（shell, uid 2000）没 token 读 /images → 要 403：" + no_token)
if not ok1:
    fails.append("no-token")

no_token_dl = probe("/downloads/any/any/1.webp")
ok2 = "403" in no_token_dl
print(("  PASS  " if ok2 else "  FAIL  ") + "没 token 读 /downloads → 要 403：" + no_token_dl)
if not ok2:
    fails.append("no-token-downloads")

with_token = probe("/images/anything/1.webp?t=" + token)
ok3 = "403" not in with_token
print(("  PASS  " if ok3 else "  FAIL  ") + "带对 token 读同一路径 → 不再 403（放行到「文件不存在」）：" + with_token)
if not ok3:
    fails.append("with-token")

bad = probe("/images/anything/1.webp?t=nope")
ok4 = "403" in bad
print(("  PASS  " if ok4 else "  FAIL  ") + "带错 token → 403：" + bad)
if not ok4:
    fails.append("bad-token")

print("\n结果：" + ("全部通过" if not fails else "失败 " + ", ".join(fails)))
sys.exit(1 if fails else 0)