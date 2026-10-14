# -*- coding: utf-8 -*-
r"""运行足迹验收：这个包到底往哪儿写东西。

用户要回答的是"会不会污染同学的本机"。做法是把包放进一个受控环境里跑一次，然后对比：

  * 假 USERPROFILE（= 同学的 C:\Users\xxx）：新文件**必须**全部落在 `<home>\.jmreader` 里；
  * 假 TEMP：**必须是空的**（onedir 不自解压，%TEMP% 里不该多出东西）；
  * 程序自己的目录：一个文件都不该多（可以放只读位置）；
  * 注册表：不新增卸载项、不动 PATH。

能证明的是上面这几条；系统级目录（%LOCALAPPDATA% 里的 WebView2 运行时缓存等）没做全盘 diff，
别过度解读。跑法：.venv\Scripts\python.exe tmp\_check_exe_footprint.py
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import subprocess
import sys
import time
import winreg
from pathlib import Path

ROOT = Path("D:/guzhu_comic")
SRC = ROOT / "build_out" / "GuzhuComic"
WORK = ROOT / "tmp" / "_exe_fp"
APP = WORK / "GuzhuComic"
HOME = WORK / "home"
TEMP = WORK / "temp"

FAILS = []


def expect(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


def snapshot(root: Path):
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(root))] = p.stat().st_size
    return out


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


def reg_uninstall_names():
    names = set()
    for hive, path in ((winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_LOCAL_MACHINE,
                        r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_LOCAL_MACHINE,
                        r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:
            with winreg.OpenKey(hive, path) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    names.add(winreg.EnumKey(k, i))
        except OSError:
            pass
    return names


def env_path():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, "Path")[0]
    except OSError:
        return ""


def main():
    if not (SRC / "GuzhuComic.exe").exists():
        print("FAIL  没有 exe（先跑 scripts\\build_exe.ps1）", flush=True)
        return 1
    if WORK.exists():
        shutil.rmtree(WORK)
    APP.parent.mkdir(parents=True)
    shutil.copytree(SRC, APP)
    HOME.mkdir(parents=True)
    TEMP.mkdir(parents=True)

    app_before = snapshot(APP)
    reg_before = reg_uninstall_names()
    path_before = env_path()

    env = dict(os.environ, USERPROFILE=str(HOME), TEMP=str(TEMP), TMP=str(TEMP))
    for key in ("HOMEDRIVE", "HOMEPATH", "HOME"):
        env.pop(key, None)

    proc = subprocess.Popen([str(APP / "GuzhuComic.exe")], cwd=str(APP), env=env)
    deadline = time.time() + 40
    while time.time() < deadline:
        if any(w == "Guzhu Comic" for w in titles_by_pid().get(proc.pid, [])):
            break
        if proc.poll() is not None:
            print("FAIL  exe 自己退了，退出码 " + str(proc.returncode), flush=True)
            return 1
        time.sleep(0.5)
    time.sleep(6)                      # 让它把缓存 / localStorage 也写出来
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True)
    time.sleep(2)

    home_new = snapshot(HOME)
    temp_new = snapshot(TEMP)
    app_new = snapshot(APP)
    jm = {k: v for k, v in home_new.items() if k.startswith(".jmreader\\") or k.startswith(".jmreader/")}
    stray = {k: v for k, v in home_new.items() if k not in jm}

    top = {}
    for rel in jm:
        seg = rel.replace("\\", "/").split("/")
        top[seg[1] if len(seg) > 1 else "(root)"] = top.get(seg[1] if len(seg) > 1 else "(root)", 0) + 1
    print("[info] 假用户目录里新文件 %d 个，分布：%s" % (len(jm), json.dumps(top, ensure_ascii=False)), flush=True)
    print("[info] 程序目录新增文件：%d 个；假 TEMP 新增：%d 个" %
          (len(set(app_new) - set(app_before)), len(temp_new)), flush=True)

    expect(bool(jm) and (HOME / ".jmreader").is_dir(), "数据落在 <home>/.jmreader 里")
    expect(not stray, "用户目录下除了 .jmreader 没有别的落点（多出来的：%s）" % list(stray)[:5])
    expect(not temp_new, "%TEMP% 里一个文件都没多（onedir 不自解压）")
    expect(set(app_new) == set(app_before), "程序自己的目录没被写（可以放只读位置）")
    expect(reg_uninstall_names() == reg_before, "注册表没新增卸载项（不装东西、不改系统）")
    expect(env_path() == path_before, "没动 HKCU 的 PATH")

    shutil.rmtree(WORK, ignore_errors=True)
    print()
    print("结果:", FAILS if FAILS else "全部通过")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
