# -*- coding: utf-8 -*-
"""阅读器浮层不做毛玻璃的回归：漫画是内容，不能被 backdrop-filter 糊掉。

探针走外部脚本（probe.js）+ `fetch('/report?d=...')` 回报给 Python 侧本地服务。
"""
import functools, http.server, os, shutil, socket, subprocess, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
function page(n, color) {
  var c = document.createElement('canvas');
  c.width = 760; c.height = 1100;
  var g = c.getContext('2d');
  g.fillStyle = '#f4f1ea'; g.fillRect(0, 0, 760, 1100);
  g.strokeStyle = color; g.lineWidth = 6;
  for (var y = 40; y < 1100; y += 46) { g.beginPath(); g.moveTo(40, y); g.lineTo(720, y); g.stroke(); }
  return c.toDataURL('image/png');
}
var P1 = page(1, '#c0392b'), P2 = page(2, '#2c6fb5');
var DETAIL = {
  id: '101', title: '玻璃测试漫画', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 2, cover_url: P1, related: [],
  chapters: [{ photo_id: '9001', index: '1', title: '第 1 话' }]
};
var stub = {
  get_settings: function () { return Promise.resolve({ reader: { mode: 'single', background: 'dark', width: 1080 } }); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_album_detail: function () { return Promise.resolve(DETAIL); },
  get_chapter: function () { return Promise.resolve({ images: [P1, P2] }); },
  get_progress: function () { return Promise.resolve(0); },
  is_favorite: function () { return Promise.resolve(false); },
  get_album_progress: function () { return Promise.resolve(null); },
  get_download: function () { return Promise.resolve(null); },
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

PROBE = """
setTimeout(function () {
  function note(text) {
    try { fetch('/report?d=' + encodeURIComponent(text)); } catch (e) {}
  }
  function bd(sel) {
    var el = document.querySelector(sel);
    if (!el) return 'missing';
    el.hidden = false;                     // 藏着的浮层也要量得到
    el.dataset.visible = 'true';
    var cs = getComputedStyle(el);
    return (cs.backdropFilter || cs.webkitBackdropFilter || 'none');
  }
  var steps = [
    function () { location.hash = '#/read?photo_id=9001&album_id=101'; },
    function () { note('hash=' + location.hash); },
    function () {
      var imgs = document.querySelectorAll('.reader-images img');
      note('imgs=' + imgs.length);
      note('top=' + bd('.reader-top'));
      note('dock=' + bd('.reader-dock'));
      note('chapters=' + bd('.reader-chapters'));
      note('settings=' + bd('.reader-settings'));
      note('end=' + bd('.reader-end'));
      note('toast=' + bd('.reader-toast'));
      var top = document.querySelector('.reader-top');
      var cs = getComputedStyle(top);
      var m = /rgba?\\([^)]*,\\s*([0-9.]+)\\)/.exec(cs.backgroundColor);
      note('topAlpha=' + (m ? m[1] : 'n/a'));
      var dock = document.querySelector('.reader-dock');
      var m2 = /rgba?\\([^)]*,\\s*([0-9.]+)\\)/.exec(getComputedStyle(dock).backgroundColor);
      note('dockAlpha=' + (m2 ? m2[1] : 'n/a'));
      var img = document.querySelector('.reader-images img');
      note('imgFilter=' + (img ? getComputedStyle(img).filter : 'missing'));
      note('DONE=1');
    }
  ];
  var i = 0;
  (function tick() {
    if (i >= steps.length) return;
    var step = steps[i];
    i += 1;
    setTimeout(function () {
      try { step(); } catch (e) { note('ERR=' + (e && e.message ? e.message : e)); }
      tick();
    }, 900);
  })();
}, 2600);
"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(http.server.SimpleHTTPRequestHandler):
    reports = []

    def do_GET(self):                       # noqa: N802
        if self.path.startswith("/report?"):
            query = urllib.parse.urlparse(self.path).query
            Handler.reports.append(urllib.parse.parse_qs(query).get("d", [""])[0])
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def main():
    Handler.reports = []
    tmp = os.path.join(tempfile.gettempdir(), "gz_reader_glass")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
    open(os.path.join(tmp, "probe.js"), "w", encoding="utf-8", newline="\n").write(PROBE)
    idx = os.path.join(tmp, "index.html")
    base = open(idx, encoding="utf-8").read().replace(
        "</head>", '<script src="/stub.js"></script></head>', 1)
    open(idx, "w", encoding="utf-8", newline="").write(
        base.replace("</body>", '<script src="/probe.js"></script></body>', 1))

    port = free_port()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.directory = tmp
    os.chdir(tmp)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_reader_glass_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=1200,900",
                        "--virtual-time-budget=20000",
                        "http://127.0.0.1:%d/#/popular" % port],
                       capture_output=True, timeout=300)
    finally:
        httpd.shutdown()
        shutil.rmtree(profile, ignore_errors=True)

    fields = {}
    for report in Handler.reports:
        if "=" in report:
            k, v = report.split("=", 1)
            fields[k] = v
    print("回报 %d 条:" % len(fields), "|".join("%s=%s" % kv for kv in fields.items()))
    shutil.rmtree(tmp, ignore_errors=True)

    if "DONE" not in fields:
        print("FAIL 探针没跑完（上面那条就是走到哪儿）")
        return 1
    none = lambda k: fields.get(k) in ("none", "")          # 没设过 / 明确 none 都算干净
    alpha = lambda k: (fields.get(k) or "0") not in ("0", "n/a")
    expect = [
        ("阅读器铺出来了", fields.get("imgs") == "2"),
        ("顶栏没有毛玻璃", none("top")),
        ("底部工具条没有毛玻璃", none("dock")),
        ("目录面板没有毛玻璃", none("chapters")),
        ("设置面板没有毛玻璃", none("settings")),
        ("单页末页卡没有毛玻璃", none("end")),
        ("翻页提示条没有毛玻璃", none("toast")),
        ("顶栏底色够实（去掉模糊后字还看得清）", alpha("topAlpha") and float(fields["topAlpha"]) >= 0.8),
        ("底部工具条底色够实", alpha("dockAlpha") and float(fields["dockAlpha"]) >= 0.8),
        ("漫画图本身没被 filter 糊", fields.get("imgFilter") == "none"),
    ]
    bad = 0
    for label, ok in expect:
        print("%s %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            bad += 1
    print("ALL PASS" if bad == 0 else "挂了 %d 条" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
