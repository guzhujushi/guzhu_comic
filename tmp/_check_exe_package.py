# -*- coding: utf-8 -*-
r"""打包态验收：真 exe（build_out 的**副本**）→ 真窗口 → 页面通过真桥回报 DOM。

为什么用副本：要在 dist/index.html 里注入一段探针脚本，绝不能碰要发出去的那个包。
回报通道走产品自己的桥（save_settings 写 window.title），不额外加任何接口 —— 顺带把
"冻结态能不能把 config.yaml 写进用户目录"这条也验了。

跑法：.venv/Scripts/python.exe tmp/_check_exe_package.py
"""
import ctypes
import ctypes.wintypes as wt
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path("D:/guzhu_comic")
SRC = ROOT / "build_out" / "GuzhuComic"
WORK = ROOT / "tmp" / "_exe_verify"
APP = WORK / "GuzhuComic"
EXE = APP / "GuzhuComic.exe"
USER_DIR = Path.home() / ".jmreader"
CFG = USER_DIR / "config.yaml"
PORT = 47753

PROBE = """<script>
(function(){
  function snap(){
    var app = document.querySelector('#app');
    var rec = document.querySelector('.rec-section');
    var resume = document.querySelector('.nav-resume');
    return 'PROBE|kids=' + (app ? app.children.length : -1)
      + '|rec=' + (rec ? (rec.hidden ? 'hidden' : 'shown') : 'none')
      + '|cards=' + document.querySelectorAll('.rec-section album-card').length
      + '|resume=' + (resume ? (resume.hidden ? 'hidden' : 'shown') : 'none')
      + '|rows=' + document.querySelectorAll('.cat-section album-card').length;
  }
  function send(text){
    var api = window.pywebview && window.pywebview.api;
    if (!api || !api.save_settings) return false;
    try { api.save_settings({ window: { title: text } }); return true; } catch (e) { return false; }
  }
  [5000, 9000].forEach(function(ms){ setTimeout(function(){ send(snap()); }, ms); });
  window.addEventListener('pywebviewready', function(){ setTimeout(function(){ send(snap()); }, 1500); });
})();
</script>"""


def titles_by_pid():
    """枚举顶层窗口 -> {pid: [标题]}"""
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


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def main():
    ok = True
    if not (SRC / "GuzhuComic.exe").exists():
        print("FAIL  没找到 exe：" + str(SRC / "GuzhuComic.exe") + "（先跑 scripts/build_exe.ps1）", flush=True)
        return False
    if CFG.exists():
        print("[setup] 已有的用户配置先备份到 config.yaml.bak", flush=True)
        shutil.copy2(CFG, str(CFG) + ".bak")

    # 1) 复制一份要发出去的包，只改副本
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(SRC, APP)
    index = APP / "_internal" / "dist" / "index.html"
    html = index.read_text(encoding="utf-8")
    if "</body>" not in html:
        print("FAIL  dist/index.html 里没有 </body>，注入点找不到", flush=True)
        return False
    index.write_text(html.replace("</body>", PROBE + "</body>"), encoding="utf-8")
    print("[setup] 副本就绪：" + str(APP), flush=True)

    # 2) 起真 exe（真窗口），等它把探针写进用户配置
    proc = subprocess.Popen([str(EXE)], cwd=str(APP))
    payload = ""
    deadline = time.time() + 40
    while time.time() < deadline:
        if CFG.exists():
            try:
                text = CFG.read_text(encoding="utf-8")
            except OSError:
                text = ""
            if "PROBE|" in text:
                payload = [ln for ln in text.splitlines() if "PROBE|" in ln][0].strip()
                break
        if proc.poll() is not None:
            print("FAIL  exe 自己退了，退出码 " + str(proc.returncode), flush=True)
            return False
        time.sleep(0.5)

    wins = titles_by_pid().get(proc.pid, [])
    print("[check] exe pid=" + str(proc.pid) + " 窗口标题=" + json.dumps(wins, ensure_ascii=False), flush=True)

    # 3) 冻结态自己的静态服务：dist + 图片（同源）
    try:
        status, body = get("http://127.0.0.1:%d/index.html" % PORT)
        served = "PROBE" in body.decode("utf-8", "replace")
        print("[check] :%d/index.html -> %s，且就是包内那份 dist：%s" % (PORT, status, served), flush=True)
        if status != 200 or not served:
            print("FAIL  静态服务没喂上包内 dist", flush=True)
            ok = False
    except Exception as e:
        print("FAIL  静态服务连不上 :%d - %r" % (PORT, e), flush=True)
        ok = False

    sample = None
    for pid_dir in sorted((USER_DIR / "cache" / "images").glob("*")):
        files = sorted(p for p in pid_dir.iterdir() if p.is_file())
        if files:
            sample = (pid_dir.name, files[0].name)
            break
    if sample:
        url = "http://127.0.0.1:%d/images/%s/%s" % (PORT, sample[0], urllib.parse.quote(sample[1]))
        try:
            status, body = get(url)
            print("[check] /images 同源取图 -> %s %dB" % (status, len(body)), flush=True)
            if status != 200 or not body:
                print("FAIL  打包态取图失败：" + url, flush=True)
                ok = False
        except Exception as e:
            print("FAIL  打包态取图炸了 %s - %r" % (url, e), flush=True)
            ok = False
    else:
        print("[check] /images 同源取图 -> skip（缓存里没有图）", flush=True)

    # 4) WebView2 的 user data 落在用户目录（localStorage 才留得住）
    wv = USER_DIR / "webview"
    wv_files = sum(1 for _ in wv.rglob("*")) if wv.exists() else 0
    print("[check] %s 里 %d 个文件" % (wv, wv_files), flush=True)
    if wv_files < 5:
        print("FAIL  WebView2 的 user data 没落到用户目录（localStorage 会丢）", flush=True)
        ok = False

    # 5) 收尾：杀掉进程树，再把被探针改过的用户配置还回去 —— 不还原的话，下一个用例读到的
    #    窗口标题就是 "PROBE|…"（_check_exe_single / _check_exe_real 都按标题找窗口）
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True)
    time.sleep(1)
    bak = Path(str(CFG) + ".bak")
    if bak.exists():
        shutil.copy2(str(bak), str(CFG))
        print("[teardown] 用户配置已从 config.yaml.bak 还原", flush=True)

    if not payload:
        print("FAIL  40 秒内没等到页面通过桥回报（页面可能压根没渲染出来）", flush=True)
        ok = False
    else:
        print("[check] 页面回报：" + payload, flush=True)
        parts = dict(kv.split("=", 1) for kv in payload.split("|")[1:])
        if parts.get("kids", "0") == "0":
            print("FAIL  exe 里 #app 是空的（整窗空白）", flush=True)
            ok = False
        if parts.get("rec") != "shown" or int(parts.get("cards", "0")) < 1:
            print("FAIL  推荐段没铺出来：" + payload, flush=True)
            ok = False
        if parts.get("resume") != "shown":
            print("FAIL  左下角「继续阅读」没铺出来：" + payload, flush=True)
            ok = False
        if int(parts.get("rows", "0")) < 1:
            print("FAIL  分类横条是空的：" + payload, flush=True)
            ok = False

    print("\n=> " + ("全部通过" if ok else "有问题，见上面的 FAIL"), flush=True)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
