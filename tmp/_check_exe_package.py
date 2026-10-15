# -*- coding: utf-8 -*-
r"""打包态验收：真 exe（build_out 的**副本**）→ 真窗口 → 页面通过真桥回报 DOM。

为什么用副本：要在 dist/index.html 里注入一段探针脚本，绝不能碰要发出去的那个包。

P0（2026-10-15）之后 /images 与 /downloads 都带 token 闸门，所以取图那条用例从启动日志里读
这次开窗的 `?t=`（页面地址上就带着它），并且**同时**验"不带 token 必须 403"。
回报通道走产品自己的桥（save_settings 写 window.title），不额外加任何接口 —— 顺带把
"冻结态能不能把 config.yaml 写进用户目录"这条也验了。

跑法：.venv/Scripts/python.exe tmp/_check_exe_package.py
"""
import ctypes
import ctypes.wintypes as wt
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
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
  [5000, 9000, 15000].forEach(function(ms){ setTimeout(function(){ send(snap()); }, ms); });
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


LOG = USER_DIR / "logs" / "app.log"

# 热更通道（前端那份）：用来核"包内这份 dist 到底是哪一版"
CHANNEL = "https://code.guzhujushi.cn/guzhujushi/guzhu_comic/raw/branch/main/web"


def digest_tree(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def digest_zip(raw: bytes) -> dict:
    out = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for e in zf.infolist():
            if e.is_dir():
                continue
            name = e.filename.replace("\\", "/")
            if name.startswith("__MACOSX/") or name.rsplit("/", 1)[-1].startswith("."):
                continue
            out[name] = hashlib.sha256(zf.read(e)).hexdigest()
    return out


def token_from_log() -> str:
    """
    这次开窗的通行证：启动日志里那行「加载地址：http://127.0.0.1:47753/?t=<token>」
    （P0 之后 /images、/downloads 都要带它，见 backend/server.py 的 _protected）。
    """
    try:
        text = LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    hits = re.findall(r"加载地址：http://127\.0\.0\.1:\d+/\?t=([A-Za-z0-9_-]+)", text)
    return hits[-1] if hits else ""


def main():
    ok = True
    if not (SRC / "GuzhuComic.exe").exists():
        print("FAIL  没找到 exe：" + str(SRC / "GuzhuComic.exe") + "（先跑 scripts/build_exe.ps1）", flush=True)
        return False
    # 端口上已经有人应答 = **别的实例**还开着（上一轮没杀干净的 / 用户自己开着的）：它会占住
    # 47753，我们这次起的实例只能退到 47754，于是后面每一条请求都打在错的那个进程上、
    # 报出来全是不着边际的 FAIL（2026-10-15 就踩过一次）。这里先说清楚。
    try:
        get("http://127.0.0.1:%d/index.html" % PORT, timeout=3)
        print("FAIL  :%d 已经有实例在应答（先关掉那个 GuzhuComic 再跑这条）" % PORT, flush=True)
        return False
    except Exception:
        pass

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
                latest = [ln for ln in text.splitlines() if "PROBE|" in ln][0].strip()
                payload = latest
                # 网络慢的时候 9 秒那张快照可能就是空的（5 类榜单 + 推荐都得现拉），所以这里等到
                # "推荐卡与横条都真有了"才收工，最迟 40 秒 —— 判定的是"铺得出来"，不是"9 秒时必须铺好"
                got = dict(kv.split("=", 1) for kv in latest.split("|")[1:])
                if int(got.get("cards", "0")) > 0 and int(got.get("rows", "0")) > 0:
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

    token = token_from_log()
    if token:
        print("[check] 从启动日志里拿到这次开窗的 token（%d 位）" % len(token), flush=True)
    else:
        print("FAIL  %s 里没有「加载地址：…?t=」那一行，取不到 token" % LOG, flush=True)
        ok = False

    sample = None
    for pid_dir in sorted((USER_DIR / "cache" / "images").glob("*")):
        files = sorted(p for p in pid_dir.iterdir() if p.is_file())
        if files:
            sample = (pid_dir.name, files[0].name)
            break
    if sample:
        bare = "http://127.0.0.1:%d/images/%s/%s" % (PORT, sample[0], urllib.parse.quote(sample[1]))
        try:
            status, body = get(bare + "?t=" + urllib.parse.quote(token, safe=""))
            print("[check] /images 带 token 同源取图 -> %s %dB" % (status, len(body)), flush=True)
            if status != 200 or not body:
                print("FAIL  打包态取图失败：" + bare, flush=True)
                ok = False
        except Exception as e:
            print("FAIL  打包态取图炸了 %s - %r" % (bare, e), flush=True)
            ok = False
        # 反例：/images 是带 token 闸门的（同机随便哪个程序都不该白读），这条得一直是 403
        try:
            status, body = get(bare)
            print("FAIL  不带 token 居然也取到图了（%s -> %s %dB）" % (bare, status, len(body)), flush=True)
            ok = False
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("[check] 不带 token 取图 -> 403（闸门在）", flush=True)
            else:
                print("FAIL  不带 token 取图报的是 %d，不是 403" % e.code, flush=True)
                ok = False
        except Exception as e:
            print("FAIL  不带 token 取图的异常看不懂：%r" % (e,), flush=True)
            ok = False
    else:
        print("[check] /images 同源取图 -> skip（缓存里没有图）", flush=True)

    # 4) 包内那份前端到底是哪一版：`backend/version.py` 的 `BUNDLED_WEB` 是打包时钉进去的构建号，
    #    也是"装完不会一开窗就被提示有新版本"的依据（updater.current_web() 就是读它）。
    #    这里核两条：① 不是空串（空串 = 打包脚本没写，老包收不到热更那种坑）；② 它若等于通道上
    #    那一版，包内 dist 就得与线上那份**逐文件一致**（否则用户拿到的页面跟"构建号说的"不是一个东西）。
    try:
        ver = (ROOT / "backend" / "version.py").read_text(encoding="utf-8")
        bundled = re.search(r'^BUNDLED_WEB\s*=\s*"([^"]*)"', ver, re.M).group(1)
        app_ver = re.search(r'^APP_VERSION\s*=\s*"([^"]*)"', ver, re.M).group(1)
        print("[check] backend/version.py: APP_VERSION=%s BUNDLED_WEB=%s" % (app_ver, bundled), flush=True)
        if not bundled:
            print("FAIL  BUNDLED_WEB 是空串（打包时没钉构建号 → 用户装完会被提示一次「有新版本」）", flush=True)
            ok = False
        remote = json.loads(urllib.request.urlopen(CHANNEL + "/manifest.json", timeout=30).read().decode("utf-8"))
        if bundled and bundled == str(remote.get("web") or ""):
            raw = urllib.request.urlopen(CHANNEL + "/" + remote["file"], timeout=120).read()
            # 比 SRC（真正要发出去的包）而不是 APP —— APP 那份的 index.html 被注了探针
            packed, online = digest_tree(SRC / "_internal" / "dist"), digest_zip(raw)
            only_local = sorted(set(packed) - set(online))
            only_online = sorted(set(online) - set(packed))
            differs = sorted(k for k in set(packed) & set(online) if packed[k] != online[k])
            same = not (only_local or only_online or differs)
            print("[check] 包内 dist vs 线上 %s：%d / %d 个文件，逐文件一致=%s"
                  % (bundled, len(packed), len(online), same), flush=True)
            if not same:
                print("FAIL  包内 dist 与线上那一版对不上（只在包内 %s / 只在线上 %s / 内容不同 %s）"
                      % (only_local, only_online, differs), flush=True)
                ok = False
        else:
            print("[check] 包内是 %s，通道上是 %s → 装完会提示一次更新（允许；只在这两版相同时才逐文件核）"
                  % (bundled or "（空）", remote.get("web")), flush=True)
    except Exception as e:
        print("FAIL  核包内前端版本这一段炸了：%r" % (e,), flush=True)
        ok = False

    # 5) WebView2 的 user data 落在用户目录（localStorage 才留得住）
    wv = USER_DIR / "webview"
    wv_files = sum(1 for _ in wv.rglob("*")) if wv.exists() else 0
    print("[check] %s 里 %d 个文件" % (wv, wv_files), flush=True)
    if wv_files < 5:
        print("FAIL  WebView2 的 user data 没落到用户目录（localStorage 会丢）", flush=True)
        ok = False

    # 6) 收尾：杀掉进程树，再把被探针改过的用户配置还回去 —— 不还原的话，下一个用例读到的
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
