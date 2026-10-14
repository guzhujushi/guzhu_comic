# -*- coding: utf-8 -*-
"""阅读器工具条「按指针位置分上下唤出」的回归。"""
import http.server, os, shutil, socket, subprocess, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
function page(n) {
  var c = document.createElement('canvas');
  c.width = 760; c.height = 1100;
  var g = c.getContext('2d');
  g.fillStyle = '#f4f1ea'; g.fillRect(0, 0, 760, 1100);
  g.fillStyle = '#111'; g.font = 'bold 96px sans-serif'; g.fillText('PAGE ' + n, 120, 240);
  return c.toDataURL('image/png');
}
var P1 = page(1), P2 = page(2);
var DETAIL = {
  id: '101', title: '工具条测试', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 2, cover_url: P1, related: [],
  chapters: [{ photo_id: '9001', index: '1', title: '第 1 话' }, { photo_id: '9002', index: '2', title: '第 2 话' }]
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
  function bars() {
    return 'top=' + document.querySelector('.reader-top').dataset.visible +
           ',dock=' + document.querySelector('.reader-dock').dataset.visible;
  }
  function move(y) {
    var e = new MouseEvent('mousemove', { clientX: 600, clientY: y, bubbles: true });
    window.dispatchEvent(e);
  }
  function sheetOpen() {
    return !document.querySelector('.reader-chapters').hidden;
  }
  function key(k) {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
  }
  var H = window.innerHeight;
  var steps = [
    function () { location.hash = '#/read?photo_id=9001&album_id=101'; },
    function () {
      note('imgs=' + document.querySelectorAll('.reader-images img').length);
      note('afterBoot=' + bars());
    },
    // 挪动和读状态必须在同一步里（分开的话 2.6s 的自动收起会插进来，测的就不是这套逻辑了）
    function () { move(40); note('nearTop=' + bars()); },      // 靠上：只出顶栏
    function () { move(H - 40); note('nearBottom=' + bars()); },  // 靠下：只出底部操作条
    function () { move(Math.round(H / 2)); note('middle=' + bars()); },
    function () { key('m'); },                     // M 键：两条都出来
    function () { note('afterM=' + bars()); },
    function () { document.querySelector('.chapters-btn').click(); },
    function () { note('sheetOpen=' + sheetOpen() + ',bars=' + bars()); },
    function () { document.querySelector('.reader-chapters .sheet-close').click(); },
    function () { note('afterClose=' + sheetOpen() + ',bars=' + bars()); },
    function () { },
    function () { },
    function () { note('afterIdle=' + bars()); note('DONE=1'); }
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_reader_bars")
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

    profile = os.path.join(tempfile.gettempdir(), "gz_reader_bars_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=1200,900",
                        "--virtual-time-budget=30000",
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
    expect = [
        ("阅读器铺出来了", fields.get("imgs") == "2"),
        ("刚进来两条都藏着", fields.get("afterBoot") == "top=false,dock=false"),
        ("指针靠上：只出顶栏", fields.get("nearTop") == "top=true,dock=false"),
        ("指针靠下：只出底部工具条", fields.get("nearBottom") == "top=false,dock=true"),
        ("屏幕中间：已经亮着的不动", fields.get("middle") == "top=false,dock=true"),
        ("M 键：两条都唤出", fields.get("afterM") == "top=true,dock=true"),
        ("开目录时底部工具条还在", fields.get("sheetOpen") == "true,bars=top=true,dock=true"),
        ("关掉目录：浮层收了、工具条还亮着", fields.get("afterClose") == "false,bars=top=true,dock=true"),
        ("停手几秒后自己收起", fields.get("afterIdle") == "top=false,dock=false"),
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
