# -*- coding: utf-8 -*-
r"""核对 router 的"页面挂载就炸"兜底。

用法：.\.venv\Scripts\python.exe tmp\_check_router_guard.py crash|normal

crash 模式需要先把 frontend/src/pages/about.ts 的 aboutPage() 改成一进来就 throw
（见 tmp/_harden_router_e2e.ps1），normal 模式是原样。
"""
import functools, http.server, os, re, shutil, socket, subprocess, sys, tempfile, threading

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MODE = (sys.argv[1] if len(sys.argv) > 1 else "normal").lower()

STUB = """
var stub = {
  get_settings: function () { return Promise.resolve({ splash: { enabled: false } }); },
  prefetch_home: function () { return Promise.resolve(null); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

MARK = """<script>
function snap() {
  var app = document.querySelector('#app');
  var t = document.querySelector('.empty-title');
  var b = document.querySelector('.empty-action');
  return 'kids=' + (app ? app.children.length : -1)
    + ',title=' + (t ? t.textContent : '-')
    + ',btn=' + (b ? b.textContent : '-');
}
setTimeout(function () {
  var a = snap();
  var btn = document.querySelector('.empty-action');
  if (btn) btn.click();
  setTimeout(function () {
    var b = snap();
    location.hash = '#/popular';
    setTimeout(function () {
      var c = 'board=' + (document.querySelector('.board-page') !== null)
        + ',title=' + (document.querySelector('.empty-title') ? document.querySelector('.empty-title').textContent : '-')
        + ',kids=' + document.querySelector('#app').children.length;
      document.title = 'R|A{' + a + '}|B{' + b + '}|C{' + c + '}';
    }, 1600);
  }, 900);
}, 1200);
</script>"""


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = os.path.join(tempfile.gettempdir(), "gz_router")
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
idx = os.path.join(tmp, "index.html")
base = open(idx, encoding="utf-8").read().replace("</head>", '<script src="/stub.js"></script></head>', 1)
open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
open(idx, "w", encoding="utf-8", newline="").write(base.replace("</body>", MARK + "</body>", 1))

port = free_port()
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port),
                                        functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
profile = os.path.join(tempfile.gettempdir(), "gz_router_chrome")
shutil.rmtree(profile, ignore_errors=True)
try:
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--user-data-dir=" + profile,
                        "--window-size=1200,900", "--virtual-time-budget=9000", "--dump-dom",
                        "http://127.0.0.1:%d/#/about" % port],
                       capture_output=True, timeout=200, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"<title>(.*?)</title>", r.stdout or "", re.S)
    title = m.group(1) if m else "NO-TITLE"
finally:
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(profile, ignore_errors=True)

print("MODE =", MODE)
print("TITLE =", title)

parts = dict(re.findall(r"([ABC])\{(.*?)\}", title))
checks = []
if MODE == "crash":
    # 兜底盒子该出来：标题 / 重试按钮都在，容器不是空的
    checks.append(("A 有兜底提示", parts.get("A", "").startswith("kids=1,title=加载失败了,btn=重试")))
    checks.append(("点重试后仍在", parts.get("B", "").startswith("kids=1,title=加载失败了,btn=重试")))
    checks.append(("切到别的页照常", parts.get("C", "").startswith("board=true")))
else:
    checks.append(("about 页正常渲染", "kids=1,title=-" in parts.get("A", "")))
    checks.append(("首页照常", parts.get("C", "").startswith("board=true")))

bad = [n for n, ok in checks if not ok]
for n, ok in checks:
    print(("PASS  " if ok else "FAIL  ") + n)
print("RESULT:", "ALL PASS" if not bad else "FAILED " + str(bad))
sys.exit(1 if bad else 0)