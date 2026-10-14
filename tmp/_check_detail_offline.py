# -*- coding: utf-8 -*-
"""详情页「离线可看 / 只下这一话」的回归（A / B 组后端补齐那轮的接线）。

核对四件事：
  1. 磁盘上有几话 → 标题上面那一行写清楚（整本已离线 / 已离线 n/m 话）；
  2. 章节行 = 章节按钮 + 「只下这一话」的小按钮（顺序不能反）；
  3. 已经在磁盘上的那话：绿色勾 + 按钮禁用；没下过的：可点；
  4. 点一下真的按 (album_id, photo_id, index) 调了 download_chapter。
"""
import http.server, os, shutil, socket, subprocess, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
var DL = [];
var DETAIL = {
  id: '101', title: '离线测试', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 3, cover_url: '', related: [],
  chapters: [
    { photo_id: '9001', index: '1', title: '第 1 话' },
    { photo_id: '9002', index: '2', title: '第 2 话' },
    { photo_id: '9003', index: '3', title: '第 3 话' }
  ]
};
var CACHED = [
  { photo_id: '9001', album_id: '101', album_title: '离线测试', index: '1', title: '第 1 话',
    state: 'done', images: 20, total: 20, bytes: 1048576, offline: true, mtime: 2 },
  { photo_id: '9002', album_id: '101', album_title: '离线测试', index: '2', title: '第 2 话',
    state: 'done', images: 18, total: 18, bytes: 1048576, offline: true, mtime: 1 }
];
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_album_detail: function () { return Promise.resolve(DETAIL); },
  get_album_progress: function () { return Promise.resolve(null); },
  is_favorite: function () { return Promise.resolve(false); },
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); },
  get_download: function () { return Promise.resolve(null); },
  is_album_offline: function () {
    return Promise.resolve({ album_id: '101', chapters: 2, done: 1, offline: false,
      images: 38, bytes: 2097152, dir: 'X:\\\\downloads\\\\101' });
  },
  list_cached_chapters: function () { return Promise.resolve(CACHED); },
  download_chapter: function (aid, pid, idx, ctitle, title, cover) {
    DL.push([aid, pid, idx].join('/'));
    return Promise.resolve({ album_id: aid, state: 'queued', running: true, done: 0, total: 1 });
  },
  __dl: function () { return DL.join(','); }
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
  function rows() { return document.querySelectorAll('.chapter-row'); }
  var steps = [
    function () { location.hash = '#/album?id=101'; },
    function () {
      var line = document.querySelector('.offline-line');
      note('offlineLine=' + (line ? line.textContent : 'missing'));
      note('chapterRows=' + rows().length);
      note('chapterItems=' + document.querySelectorAll('.chapter-item').length);
      note('marked=' + document.querySelectorAll('.chapter-dl.on').length);
      var r0 = rows()[0], r2 = rows()[2];
      note('rowOrder0=' + (r0 ? r0.children[0].className + '>' + r0.children[1].className : 'missing'));
      note('cachedDisabled=' + (r0 ? r0.querySelector('.chapter-dl').disabled : 'missing'));
      note('freshDisabled=' + (r2 ? r2.querySelector('.chapter-dl').disabled : 'missing'));
    },
    function () {
      var r2 = rows()[2];
      if (r2) r2.querySelector('.chapter-dl').click();
    },
    function () {
      note('dlCalls=' + window.pywebview.api.__dl());
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_detail_offline")
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

    profile = os.path.join(tempfile.gettempdir(), "gz_detail_offline_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=1200,900",
                        "--virtual-time-budget=25000",
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
        ("离线那一行按「只下过一半」如实写", (fields.get("offlineLine") or "").find("已离线 1/2 话") >= 0),
        ("三话三行", fields.get("chapterRows") == "3"),
        ("章节按钮也还是三个", fields.get("chapterItems") == "3"),
        ("磁盘上那两话打了勾", fields.get("marked") == "2"),
        ("一行里先章节按钮后下载按钮", (fields.get("rowOrder0") or "").startswith("chapter-item>chapter-dl")),
        ("下过的那话按钮禁用", fields.get("cachedDisabled") == "true"),
        ("没下过的那话可点", fields.get("freshDisabled") == "false"),
        ("点一下调了 download_chapter(101, 9003, 3)", fields.get("dlCalls") == "101/9003/3"),
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
