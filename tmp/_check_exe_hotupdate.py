# -*- coding: utf-8 -*-
r"""打包态热更验收：真 exe 走一遍**线上更新通道**。

为什么非要在 exe 上验：源码态 `_check_updater.py` 只验到 `paths.web_dist_dir()` 那一层，而
"热更装了到底生不生效"取决于**打包后那个本地静态服务**是否每请求重挑根（`backend/server.py` 的
`translate_path` → `_pick_root`）。这一条只有真 exe + 真窗口 + 真 HTTP 请求才证明得了。

做法：
  1. 复制要发出去的那个包（**不动** `build_out\` 里的原件），往副本的 `_internal\dist\index.html`
     注入探针；探针依次调 `check_update` → `apply_update` → `fetch('/version.json')`；
  2. 假 `USERPROFILE`（= 全新首启，配置与覆盖层都从零）起真 exe；
  3. 关键的那一步是 `fetch('/version.json')`：**包内 dist 里没有** version.json，只有覆盖层里才有
     （`updater._swap` 写进去的）—— 它 200 且带对的构建号，就等于"静态服务真换成覆盖层了"；
  4. 探针怎么把结果送回来：**不用** `save_settings` 那条路（应用自己会写回 window.title，撞车），
     改成页面 `fetch('http://127.0.0.1:<测试进程的端口>/?d=…', {mode:'no-cors'})`，测试进程收。

跑法：.venv\Scripts\python.exe tmp\_check_exe_hotupdate.py
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path("D:/guzhu_comic")
SRC = ROOT / "build_out" / "GuzhuComic"
WORK = ROOT / "tmp" / "_exe_hu"
APP = WORK / "GuzhuComic"
HOME = WORK / "home"
TEMP = WORK / "temp"
CFG = HOME / ".jmreader" / "config.yaml"
CHANNEL = "https://code.guzhujushi.cn/guzhujushi/guzhu_comic/raw/branch/main/web"

FAILS = []
REPORTS = []


def expect(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


class Sink(BaseHTTPRequestHandler):
    """页面把结果打过来（no-cors，所以不用管 CORS 头，但还是给上）"""

    def log_message(self, *a):
        pass

    def do_GET(self):
        q = parse_qs(urlsplit(self.path).query)
        data = (q.get("d") or [""])[0]
        if data:
            REPORTS.append(data)
            print("  [page] " + data, flush=True)
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def probe_js(port: int) -> str:
    return """<script>
(function(){
  var REPORT = 'http://127.0.0.1:%d/?d=';
  function send(t){ try { fetch(REPORT + encodeURIComponent(t), {mode:'no-cors'}); } catch(e){} }
  function brief(v){ return String(v === undefined || v === null ? '' : v).replace(/[^0-9A-Za-z_=.:-]/g, '_').slice(0, 44); }
  send('HU1 boot ready=' + document.readyState);
  var started = false;
  async function run(){
    if (started) return;
    var api = window.pywebview && window.pywebview.api;
    if (!api || !api.check_update) return;
    started = true;
    send('HU2 bridge api=' + (typeof api.check_update));
    try {
      var c = await api.check_update();
      send('HU3 check err=[' + brief(c.error) + '] avail=' + c.available + ' web=' + brief(c.web) + ' app_min=' + brief(c.app_min));
      await new Promise(function(r){ setTimeout(r, 800) });
      var a = await api.apply_update();
      send('HU4 apply ok=' + a.ok + ' changed=' + a.changed + ' files=' + a.files + ' web=' + brief(a.web));
      await new Promise(function(r){ setTimeout(r, 1500) });
      var resp = await fetch('/version.json?t=' + Date.now(), {cache:'no-store'});
      var body = await resp.text();
      var served = '';
      try { served = JSON.parse(body).web || ''; } catch (e) { served = 'PARSE_FAIL' }
      send('HU5 served status=' + resp.status + ' srv=' + brief(served) + ' bytes=' + body.length);
      await new Promise(function(r){ setTimeout(r, 800) });
      var v = await api.get_version();
      send('HU6 version web=' + brief(v.web) + ' overlay=' + v.overlay + ' app=' + brief(v.app));
    } catch (e) {
      send('HU9 error ' + brief(e && e.message ? e.message : e));
    }
  }
  window.addEventListener('pywebviewready', function(){ send('HU1b pywebviewready'); setTimeout(run, 800) });
  var tries = 0;
  var iv = setInterval(function(){ tries++; run(); if (started || tries > 40) clearInterval(iv); }, 500);
})();
</script>""" % port


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
        print("FAIL  没找到 exe：" + str(SRC), flush=True)
        return False

    live = json.loads(urllib.request.urlopen(CHANNEL + "/manifest.json", timeout=20).read().decode("utf-8"))
    print("线上构建号 %s" % live["web"], flush=True)

    sink = ThreadingHTTPServer(("127.0.0.1", 0), Sink)
    sink_port = sink.server_address[1]
    threading.Thread(target=sink.serve_forever, daemon=True).start()
    print("[setup] 结果回收端口 %d" % sink_port, flush=True)

    if WORK.exists():
        shutil.rmtree(WORK)
    HOME.mkdir(parents=True)
    TEMP.mkdir(parents=True)
    shutil.copytree(SRC, APP)

    index = APP / "_internal" / "dist" / "index.html"
    html = index.read_text(encoding="utf-8")
    expect("</body>" in html, "副本 dist/index.html 里有注入点")
    index.write_text(html.replace("</body>", probe_js(sink_port) + "</body>"), encoding="utf-8")
    expect(not (APP / "_internal" / "dist" / "version.json").exists(),
           "对照组：包内 dist 里本来**没有** version.json（它出现只能来自覆盖层）")

    env = dict(os.environ)
    env["USERPROFILE"] = str(HOME)
    env["TEMP"] = str(TEMP)
    env["TMP"] = str(TEMP)
    proc = subprocess.Popen([str(APP / "GuzhuComic.exe")], cwd=str(APP), env=env)
    print("[run] exe 起来了（pid %d），等页面回报…" % proc.pid, flush=True)

    deadline = time.time() + 150
    while time.time() < deadline:
        if any(r.startswith("HU6") or r.startswith("HU9") for r in REPORTS):
            break
        if proc.poll() is not None:
            print("FAIL  exe 自己退了，退出码 %s" % proc.returncode, flush=True)
            break
        time.sleep(0.25)

    expect(len(REPORTS) > 0, "页面把探针送回来了（收到 %d 条）" % len(REPORTS))
    joined = "\n".join(REPORTS)
    wins = titles_by_pid().get(proc.pid, [])
    expect(len(wins) > 0, "真窗口还在（标题：%s）" % (wins[:1] or "无"))

    h3 = next((r for r in REPORTS if r.startswith("HU3")), "")
    h4 = next((r for r in REPORTS if r.startswith("HU4")), "")
    h5 = next((r for r in REPORTS if r.startswith("HU5")), "")
    h6 = next((r for r in REPORTS if r.startswith("HU6")), "")

    expect("HU3 check err=[]" in h3, "exe 里 check_update 没报错（%s）" % h3)
    expect("avail=true" in h3, "exe 里 check_update 认得出有新版（%s）" % h3)
    expect(live["web"] in h3, "exe 报的构建号 = 线上那个（%s）" % h3)
    expect("app_min=0.1.1" in h3, "exe 读到的 app_min 是 0.1.1（%s）" % h3)
    expect("ok=true" in h4, "exe 里 apply_update 成功（%s）" % h4)
    expect(live["web"] in h4, "装的就是线上那一版（%s）" % h4)
    expect("status=200" in h5 and live["web"] in h5,
           "装完请求 /version.json → 200 且带新构建号 → **静态服务真用上覆盖层了**（%s）" % h5)
    expect("overlay=true" in h6 and live["web"] in h6, "get_version 认覆盖层（%s）" % h6)

    overlay = HOME / ".jmreader" / "web"
    expect((overlay / "index.html").is_file(), "假家目录里落了覆盖层 index.html")
    expect((overlay / "version.json").is_file(), "假家目录里落了覆盖层 version.json")
    expect((overlay / "assets").is_dir(), "假家目录里落了覆盖层 assets/")
    expect(not (HOME / ".jmreader" / "web.old").exists(), "首启没有上一版，不该有 web.old")

    try:
        proc.terminate()
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    sink.shutdown()

    print("\n%s" % ("全部通过" if not FAILS else "失败 %d 项：%s" % (len(FAILS), "；".join(FAILS))), flush=True)
    return not FAILS


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
