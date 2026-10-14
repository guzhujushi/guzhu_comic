# -*- coding: utf-8 -*-
"""核对阅读器浮层：面板开着时，点面板外面只收面板（不翻页 / 不切面板成后立刻被关掉）。"""
import functools, http.server, os, re, shutil, socket, subprocess, tempfile, threading
REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STUB = """
var IMG = '/apple-touch-icon.png';
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  get_history: function () { return Promise.resolve([]); },
  prefetch_home: function () { return Promise.resolve(null); },
  get_progress: function () { return Promise.resolve(0); },
  save_progress: function () { return Promise.resolve(null); },
  get_chapter: function () { return Promise.resolve({ photo_id: '530000', images: [IMG, IMG, IMG] }); },
  get_album_detail: function () {
    return Promise.resolve({ id: '209827', title: '测试本子', author: 'x', authors: [], description: '',
      tags: [], likes: '1', views: '2', page_count: 3, cover_url: IMG, comment_count: '0',
      pub_date: '', update_date: '', related: [],
      chapters: [ { photo_id: '530000', index: '1', title: '第 1 话' },
                  { photo_id: '530001', index: '2', title: '第 2 话' },
                  { photo_id: '530002', index: '3', title: '第 3 话' } ] });
  }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""
MARK = """<script>setTimeout(function(){
  var root = document.querySelector('.reader');
  var imgs = document.querySelector('.reader-images');
  var chBtn = document.querySelector('.chapters-btn');
  var stBtn = document.querySelector('.settings-btn');
  var ch = document.querySelector('.reader-chapters');
  var st = document.querySelector('.reader-settings');
  var steps = [
    ['start',  null,       0, 0],
    ['ch',     chBtn,      1, 0],
    ['imgs',   imgs,       0, 0],
    ['ch',     chBtn,      1, 0],
    ['st',     stBtn,      0, 1],
    ['imgs',   imgs,       0, 0],
    ['st',     stBtn,      0, 1],
    ['root',   root,       0, 0],
    ['ch',     chBtn,      1, 0],
    ['ch',     chBtn,      0, 0]
  ];
  var out = [];
  var bad = [];
  steps.forEach(function (s) {
    if (s[1]) s[1].click();
    var got = (ch.hidden ? 0 : 1) + ',' + (st.hidden ? 0 : 1);
    var want = s[2] + ',' + s[3];
    out.push(s[0] + '=' + got + (got === want ? '' : '(want ' + want + ')'));
    if (got !== want) bad.push(s[0] + ':' + got + '!=' + want);
  });
  document.title = 'R|' + out.join(' ') + '|' + (bad.length ? 'FAIL ' + bad.join(' ') : 'ALL PASS');
}, 3000);</script>"""

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

tmp = os.path.join(tempfile.gettempdir(), "gz_reader")
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
idx = os.path.join(tmp, "index.html")
html = open(idx, encoding="utf-8").read().replace("</head>", '<script src="/stub.js"></script></head>', 1)
open(idx, "w", encoding="utf-8", newline="").write(html.replace("</body>", MARK + "</body>", 1))
port = free_port()
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
profile = os.path.join(tempfile.gettempdir(), "gz_reader_chrome")
shutil.rmtree(profile, ignore_errors=True)
try:
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--user-data-dir=" + profile,
                        "--window-size=1200,900", "--virtual-time-budget=12000", "--dump-dom",
                        "http://127.0.0.1:%d/#/read?photo_id=530000&album_id=209827" % port],
                       capture_output=True, timeout=200, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"<title>(.*?)</title>", r.stdout or "", re.S)
    print("TITLE:", (m.group(1)[:900] if m else "no title"))
finally:
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(profile, ignore_errors=True)