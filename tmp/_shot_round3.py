# -*- coding: utf-8 -*-
r"""第三轮三件事的验收截图（无头 Chrome + 假桥）：空状态字标 / 快捷键面板 / 防社死 / 搜索联想。
产物落 tmp/_ui/r3-*.png。"""
import functools, http.server, os, shutil, socket, subprocess, sys, tempfile, threading

REPO = r"D:\guzhu_comic"
OUT = os.path.join(REPO, "tmp", "_ui")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(null); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_search_log: function () { return Promise.resolve([{ keyword: '火影', count: 3, at: 2 }]); },
  get_favorites: function () {
    return Promise.resolve([{ album_id: '1', title: '火影忍者 同人集', cover_url: '', added_at: 1, favorited: true }]);
  },
  log_search: function () { return Promise.resolve(null); }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

# name, hash, w, h, 虚拟时间, 到点前执行的 JS
SHOTS = [
    ("r3-empty-brand", "#/search", 1200, 900, 4200, ""),
    ("r3-hotkey-panel", "#/popular", 1200, 900, 4200,
     "window.dispatchEvent(new KeyboardEvent('keydown',{key:'?',bubbles:true,cancelable:true}));"),
    ("r3-panic", "#/popular", 1200, 900, 4200,
     "window.dispatchEvent(new KeyboardEvent('keydown',{key:'p',bubbles:true,cancelable:true}));"),
    ("r3-search-suggest", "#/search", 1200, 900, 4200,
     "var i=document.querySelector('#keyword');i.value='火';i.dispatchEvent(new Event('input',{bubbles:true}));"),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    tmp = os.path.join(tempfile.gettempdir(), "gz_shot_round3")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
    idx = os.path.join(tmp, "index.html")
    html = open(idx, encoding="utf-8").read().replace(
        "</head>", '<script src="/stub.js"></script></head>', 1)
    assert "stub.js" in html

    port = free_port()
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_shot_round3_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    url = "http://127.0.0.1:%d/" % port
    try:
        for name, frag, w, h, budget, extra in SHOTS:
            body = ("<script>setTimeout(function(){%s},2400);</script>" % extra) if extra else ""
            open(idx, "w", encoding="utf-8", newline="").write(
                html.replace("</body>", body + "</body>", 1))
            png = os.path.join(OUT, "%s.png" % name)
            cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                   "--user-data-dir=" + profile, "--screenshot=" + png,
                   "--window-size=%d,%d" % (w, h), "--virtual-time-budget=%d" % budget,
                   "--force-device-scale-factor=1", url + frag]
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            print("截图 %-20s rc=%d %s" % (name, r.returncode,
                  os.path.getsize(png) if os.path.exists(png) else "缺失"))
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


main()
