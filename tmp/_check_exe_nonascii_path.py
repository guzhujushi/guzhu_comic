# -*- coding: utf-8 -*-
r"""中文路径验收：把包丢进带中文 / 带空格的目录里，看还能不能起。

同学把 zip 解压到「漫画工具」「我的漫画」这种文件夹是常态，而冻结态的前端 dist 是从
<exe>/_internal/dist 用本地 HTTP 服务喂出来的 —— 路径里带非 ASCII 字符时会不会挂，
只有真跑一次才知道。

跑法：.venv\Scripts\python.exe tmp\_check_exe_nonascii_path.py
"""
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("D:/guzhu_comic")
SRC = ROOT / "build_out" / "GuzhuComic"
WORK = ROOT / "tmp" / "_exe_cn"
MIDDLE = "漫画 工具"                      # 中文 + 空格 + 不常见的组合
APP = WORK / MIDDLE / "GuzhuComic"
FAKE_HOME = WORK / "用户 张三"             # 模拟"用户名是中文"的机器（Path.home() 在 Windows 上读 USERPROFILE）
PORT = 47753

FAILS = []


def expect(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


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
    if not (SRC / "GuzhuComic.exe").exists():
        print("FAIL  没有 exe（先跑 scripts\\build_exe.ps1）", flush=True)
        return 1
    if WORK.exists():
        shutil.rmtree(WORK)
    APP.parent.mkdir(parents=True)
    shutil.copytree(SRC, APP)
    print("[setup] 副本放在：" + str(APP), flush=True)

    proc = subprocess.Popen([str(APP / "GuzhuComic.exe")], cwd=str(APP))
    deadline = time.time() + 40
    wins = []
    while time.time() < deadline:
        wins = titles_by_pid().get(proc.pid, [])
        if any(w == "Guzhu Comic" for w in wins):
            break
        if proc.poll() is not None:
            print("FAIL  exe 自己退了，退出码 " + str(proc.returncode), flush=True)
            return 1
        time.sleep(0.5)
    expect(any(w == "Guzhu Comic" for w in wins), "中文路径下窗口起得来（标题 %s）" % wins[:1])

    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/index.html" % PORT, timeout=8) as r:
            body = r.read()
        expect(r.status == 200 and b"</html>" in body,
               "中文路径下的静态服务能喂出 dist（%d 字节）" % len(body))
    except Exception as e:
        expect(False, "中文路径下静态服务连不上：%r" % (e,))

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True)
    time.sleep(1)

    # 第二阶段：用户名是中文的机器（`~/.jmreader` 也跟着带中文）
    FAKE_HOME.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, USERPROFILE=str(FAKE_HOME))
    for key in ("HOMEDRIVE", "HOMEPATH", "HOME"):
        env.pop(key, None)
    proc = subprocess.Popen([str(APP / "GuzhuComic.exe")], cwd=str(APP), env=env)
    deadline = time.time() + 40
    wins = []
    while time.time() < deadline:
        wins = titles_by_pid().get(proc.pid, [])
        if any(w == "Guzhu Comic" for w in wins):
            break
        if proc.poll() is not None:
            print("FAIL  中文用户目录下 exe 自己退了，退出码 " + str(proc.returncode), flush=True)
            return 1
        time.sleep(0.5)
    expect(any(w == "Guzhu Comic" for w in wins), "中文用户名（%s）下窗口也起得来" % FAKE_HOME.name)
    user_dir = FAKE_HOME / ".jmreader"
    expect((user_dir / "config.yaml").exists(), "首启把 config.yaml 写进了中文用户目录")
    log = user_dir / "logs" / "app.log"
    expect(log.exists() and "孤竹漫画启动" in log.read_text(encoding="utf-8", errors="replace"),
           "日志也落在中文用户目录里（%s）" % log)
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/index.html" % PORT, timeout=8) as r:
            expect(r.status == 200, "中文用户目录下静态服务照常")
    except Exception as e:
        expect(False, "中文用户目录下静态服务连不上：%r" % (e,))

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True)
    time.sleep(1)
    real_home = Path.home()
    got = [p for p in FAKE_HOME.rglob("*") if p.is_file()]
    print("[info] 中文用户目录里留下了 %d 个文件（模拟机环境，收尾删掉）" % len(got), flush=True)
    shutil.rmtree(WORK, ignore_errors=True)

    print()
    print("结果:", FAILS if FAILS else "全部通过")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
