# -*- coding: utf-8 -*-
"""详情页「作者 / 标签可点 → 按条件搜」的回归。"""
import http.server, os, shutil, socket, subprocess, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
var CALLS = [];
var DETAIL = {
  id: '101', title: '可点测试', author: '测试作者', authors: ['测试作者'], description: '简介',
  tags: ['标签A', '标签 B/C'], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 1, cover_url: '', related: [],
  chapters: [{ photo_id: '9001', index: '1', title: '第 1 话' }]
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
  get_search_log: function () { return Promise.resolve([]); },
  log_search: function () { return Promise.resolve(null); },
  search: function (kw, page, scope, order) {
    CALLS.push([kw, scope].join('/'));
    return Promise.resolve([]);
  },
  is_favorite: function () { return Promise.resolve(false); },
  get_album_progress: function () { return Promise.resolve(null); },
  get_download: function () { return Promise.resolve(null); },
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); },
  __calls: function () { return CALLS.join(','); }
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
  function click(sel, label) {
    var el = document.querySelector(sel);
    if (!el) throw new Error(label + '找不到 ' + sel);
    el.click();
  }
  var steps = [
    function () { location.hash = '#/album?id=101'; },
    function () {
      var a = document.querySelector('.meta-link');
      note('authorHref=' + (a ? a.getAttribute('href') : 'missing'));
      note('tagCount=' + document.querySelectorAll('.tags a.tag').length);
      note('tagHrefs=' + [].map.call(document.querySelectorAll('.tags a.tag'), function (a) {
        return a.getAttribute('href'); }).join('|'));
      note('tagTexts=' + [].map.call(document.querySelectorAll('.tags a.tag'), function (a) {
        return a.textContent; }).join('|'));
    },
    function () { click('.meta-link', '作者链接'); },
    function () {
      note('hashAfterAuthor=' + location.hash);
      note('callsAfterAuthor=' + window.pywebview.api.__calls());
      note('scopePicker=' + ([].map.call(document.querySelectorAll('.picker-current, .picker-btn'),
        function (e) { return e.textContent.trim(); }).join(',')));
    },
    function () { location.hash = '#/album?id=101'; },
    function () { click('.tags a.tag', '第一个标签'); },
    function () {
      note('hashAfterTag=' + location.hash);
      note('callsAfterTag=' + window.pywebview.api.__calls());
      note('keywordBox=' + (document.querySelector('#keyword') ? document.querySelector('#keyword').value : 'missing'));
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_detail_links")
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

    profile = os.path.join(tempfile.gettempdir(), "gz_detail_links_chrome")
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
    author = urllib.parse.quote("测试作者")
    taga = urllib.parse.quote("标签A")
    expect = [
        ("作者是可点的链接", (fields.get("authorHref") or "") == "#/search?scope=author&q=" + author),
        ("两个标签都是链接", fields.get("tagCount") == "2"),
        ("标签链接带 scope=tag", (fields.get("tagHrefs") or "").startswith(
            "#/search?scope=tag&q=" + taga + "|")),
        ("标签文字没被转义弄坏", (fields.get("tagTexts") or "").startswith("标签A|标签 B/C")),
        ("点作者跳到作者的搜索", (fields.get("hashAfterAuthor") or "") == "#/search?q=" + author + "&scope=author"),
        ("搜索真的按 author 范围发了", "测试作者/author" in (fields.get("callsAfterAuthor") or "")),
        ("点标签跳到标签的搜索", (fields.get("hashAfterTag") or "") == "#/search?q=" + taga + "&scope=tag"),
        ("搜索真的按 tag 范围发了", "标签A/tag" in (fields.get("callsAfterTag") or "")),
        ("关键词也填进搜索框了", fields.get("keywordBox") == "标签A"),
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
