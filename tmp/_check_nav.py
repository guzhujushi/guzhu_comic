# -*- coding: utf-8 -*-
"""核对左下角「继续阅读」：卡片文案 / 链接 / 按钮点击后的 hash，以及没有记录时整块藏起来。"""
import functools, http.server, os, re, shutil, socket, subprocess, tempfile, threading
REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ITEM = ("[{album_id:'422866',photo_id:'530000',page_index:41,title:'测试本子',"
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
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""
MARK = """<script>setTimeout(function(){
  var el = document.querySelector('.nav-resume');
  var card = el.querySelector('.resume-card');
  var before = 'hidden=' + el.hidden + ',title=' + card.querySelector('.resume-title').textContent
             + ',sub=' + card.querySelector('.resume-sub').textContent
             + ',href=' + card.getAttribute('href');
  el.querySelector('.nav-resume-go').click();
  setTimeout(function(){
    document.title = 'R|' + before + '|afterClickHash=' + location.hash
      + '|cardVisible=' + (card.offsetParent !== null)
      + '|btnTitle=' + document.querySelector('.nav-resume-go').title;
  }, 400);
}, 2500);</script>"""

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

tmp = os.path.join(tempfile.gettempdir(), "gz_check")
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
idx = os.path.join(tmp, "index.html")
base = open(idx, encoding="utf-8").read().replace("</head>", '<script src="/stub.js"></script></head>', 1)
port = free_port()
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
profile = os.path.join(tempfile.gettempdir(), "gz_check_chrome")
shutil.rmtree(profile, ignore_errors=True)
try:
    for tag, hist in (("with-history", ITEM), ("no-history", "[]")):
        open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB.replace("HISTORY_JS", hist))
        open(idx, "w", encoding="utf-8", newline="").write(base.replace("</body>", MARK + "</body>", 1))
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--user-data-dir=" + profile,
                            "--window-size=1200,900", "--virtual-time-budget=9000", "--dump-dom",
                            "http://127.0.0.1:%d/#/popular" % port],
                           capture_output=True, timeout=200, text=True, encoding="utf-8", errors="replace")
        m = re.search(r"<title>(.*?)</title>", r.stdout or "", re.S)
        print(tag, "->", (m.group(1)[:400] if m else "no title"))
finally:
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(profile, ignore_errors=True)