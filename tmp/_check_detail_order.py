# -*- coding: utf-8 -*-
"""详情页区块顺序的回归：章节列表必须铺在「相关作品」**前面**。

用户要求：章节渲染到相关作品前面。
探针走外部脚本（probe.js）+ `fetch('/report?d=...')` 回报给 Python 侧本地服务
（dump-dom / document.title 那条路偶尔读不到，白耗时间）。
"""
import http.server, os, shutil, socket, subprocess, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
var DETAIL = {
  id: '101', title: '顺序测试漫画', author: '作者', authors: ['作者'], description: '简介文字',
  tags: ['标签A'], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 3, cover_url: '',
  related: [
    { id: '201', title: '相关作品甲', author: '作者甲', cover_url: '' },
    { id: '202', title: '相关作品乙', author: '作者乙', cover_url: '' }
  ],
  chapters: [
    { photo_id: '9001', index: '1', title: '第 1 话' },
    { photo_id: '9002', index: '2', title: '第 2 话' },
    { photo_id: '9003', index: '3', title: '第 3 话' }
  ]
};
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_album_detail: function () { return Promise.resolve(DETAIL); },
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
  var steps = [
    function () { location.hash = '#/album?id=101'; },
    function () { note('hash=' + location.hash); },
    function () {
      var main = document.querySelector('.detail-main');
      if (!main) { note('ERR=详情页没铺出来'); note('DONE=1'); return; }
      var titles = [].map.call(main.querySelectorAll('.section-title'), function (el) {
        return el.textContent.trim();
      });
      note('titles=' + titles.join(' > '));
      var order = [].map.call(main.children, function (el) {
        if (el.querySelector && el.querySelector('.chapter-list')) return '章节';
        if (el.classList.contains('section-title') && el.textContent.indexOf('章节') === 0) return '章节标题';
        if (el.classList.contains('section-title') && el.textContent.indexOf('相关作品') === 0) return '相关标题';
        if (el.classList.contains('related-list')) return '相关列表';
        if (el.classList.contains('chapter-list')) return '章节列表';
        if (el.classList.contains('chapter-actions')) return '章节按钮';
        if (el.classList.contains('desc')) return '简介';
        return null;
      }).filter(function (x) { return x; });
      note('order=' + order.join(' > '));
      note('chapters=' + main.querySelectorAll('.chapter-item').length);
      note('related=' + main.querySelectorAll('.related-list album-card').length);
      // 直接问 DOM：章节标题是不是排在相关作品标题前面
      var chTitle = null, relTitle = null;
      [].forEach.call(main.querySelectorAll('.section-title'), function (el) {
        if (el.textContent.indexOf('章节') === 0 && !chTitle) chTitle = el;
        if (el.textContent.indexOf('相关作品') === 0 && !relTitle) relTitle = el;
      });
      var relList = main.querySelector('.related-list');
      note('bothSectionTitles=' + (!!chTitle && !!relTitle));
      note('chapterTitleBeforeRelated=' + (!!chTitle && !!relTitle &&
        !!(chTitle.compareDocumentPosition(relTitle) & Node.DOCUMENT_POSITION_FOLLOWING)));
      var chList = main.querySelector('.chapter-list');
      note('chapterListBeforeRelatedList=' + (!!chList && !!relList &&
        !!(chList.compareDocumentPosition(relList) & Node.DOCUMENT_POSITION_FOLLOWING)));
      var desc = main.querySelector('.desc');
      note('descBeforeChapters=' + (!!desc && !!chTitle &&
        !!(desc.compareDocumentPosition(chTitle) & Node.DOCUMENT_POSITION_FOLLOWING)));
      // 折叠按钮跟章节列表待在一起，别被相关作品隔开
      var acts = main.querySelector('.chapter-actions');
      var chLast = chList ? chList.querySelector('.chapter-item:last-of-type') : null;
      note('actionsRightAfterChapters=' + (!!acts && !!chLast &&
        !!(chLast.compareDocumentPosition(acts) & Node.DOCUMENT_POSITION_FOLLOWING) &&
        !!acts.compareDocumentPosition(relList) && !!(acts.compareDocumentPosition(relList) & Node.DOCUMENT_POSITION_FOLLOWING)));
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_detail_order")
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

    profile = os.path.join(tempfile.gettempdir(), "gz_detail_order_chrome")
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
        ("详情页铺出来了", (fields.get("hash") or "") == "#/album?id=101"),
        ("两个区块标题都在", fields.get("bothSectionTitles") == "true"),
        ("章节标题在相关作品标题前面", fields.get("chapterTitleBeforeRelated") == "true"),
        ("章节列表在相关作品列表前面", fields.get("chapterListBeforeRelatedList") == "true"),
        ("简介仍在章节前面", fields.get("descBeforeChapters") == "true"),
        ("折叠按钮紧跟着章节列表（没被相关作品隔开）", fields.get("actionsRightAfterChapters") == "true"),
        ("章节按数据铺全（3 话）", fields.get("chapters") == "3"),
        ("相关作品按数据铺全（2 张）", fields.get("related") == "2"),
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
