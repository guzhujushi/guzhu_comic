# -*- coding: utf-8 -*-
"""临时预览：dist 拷到临时目录，插一段假 pywebview 桥，起本地静态服务，无头 Chrome 截图。
桩子不能用裸 Proxy：Promise.resolve(proxy) 会去读 then，代理回一个函数就把自己当 thenable，
promise 永远不 settle，主进程就卡在 waitForPywebview() 上了（踩过）。"""
import functools, http.server, os, shutil, socket, subprocess, tempfile, threading

REPO = r"D:\guzhu_comic"
OUT = os.path.join(REPO, "tmp", "_ui")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

HISTORY = ("[{album_id:'422866',photo_id:'530000',page_index:41,"
           "title:'测试用漫画标题，故意长一点看两行截断',"
           "cover_url:'/apple-touch-icon.png',updated_at:1750000000}]")

STUB = """
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(null); },
  get_ranking: function () { return Promise.resolve([]); },
  get_albums: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve(HISTORY_JS); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); }
};
window.pywebview = { api: new Proxy(stub, {
  get: function (t, k) {
    if (k === 'then') return undefined;
    if (k in t) return t[k];
    return function () { return Promise.resolve(null); };
  }
}) };
"""

SHOTS = [
    ("nav-resume", "#/popular", 1200, 900, HISTORY, ""),
    ("nav-resume-narrow", "#/popular", 1040, 800, HISTORY, ""),
    ("nav-resume-empty", "#/popular", 1200, 900, "[]", ""),
    ("nav-resume-light", "#/popular", 1200, 900, HISTORY, "document.documentElement.dataset.theme='light';"),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    tmp = os.path.join(tempfile.gettempdir(), "gz_preview")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    idx = os.path.join(tmp, "index.html")
    html = open(idx, encoding="utf-8").read().replace("</head>", '<script src="/stub.js"></script></head>', 1)
    assert "stub.js" in html

    port = free_port()
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_preview_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        for name, frag, w, h, hist, extra in SHOTS:
            open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(
                STUB.replace("HISTORY_JS", hist))
            body = ("<script>setTimeout(function(){%s},2000);</script>" % extra) if extra else ""
            open(idx, "w", encoding="utf-8", newline="").write(html.replace("</body>", body + "</body>", 1))
            png = os.path.join(OUT, "v8-%s.png" % name)
            cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                   "--user-data-dir=" + profile, "--screenshot=" + png,
                   "--window-size=%d,%d" % (w, h), "--virtual-time-budget=9000",
                   "--force-device-scale-factor=1",
                   "http://127.0.0.1:%d/%s" % (port, frag)]
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            print(name, "rc=%d" % r.returncode, os.path.getsize(png) if os.path.exists(png) else "缺失")
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


main()