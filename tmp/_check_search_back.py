# -*- coding: utf-8 -*-
"""搜索页「进详情再返回」的回归（无头 Chrome + 假桥 + dist 副本）。

流程照用户报的那条走：首页 → 搜索 → 搜一个词 → 点第一张卡进详情 → 点详情页「返回」。
期望：回来的是**带关键词的那条搜索记录**（地址栏 `?q=`、输入框还是那个词、结果重新铺出来），
换词再搜也不该在历史里堆记录（再返回一次就离开搜索页、回到首页）。

探针走外部脚本（probe.js）+ `fetch('/report?d=...')` 回报，Python 侧从本地服务收 —— 不依赖
dump-dom / document.title（试过，偶尔读不到，白耗时间）。"""
import functools, http.server, os, re, shutil, socket, subprocess, sys, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
KW = "测试"
KW2 = "漫画"

STUB = """
var LOG_CALLS = 0;
var ALBUMS = [];
for (var i = 1; i <= 6; i++) {
  ALBUMS.push({ id: '10' + i, title: '测试用漫画 ' + i, cover_url: '', favorited: false });
}
var DETAIL = {
  id: '101', title: '测试用漫画 1', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
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
  search: function () { return Promise.resolve(ALBUMS); },
  get_search_log: function () { return Promise.resolve([]); },
  log_search: function () { LOG_CALLS += 1; return Promise.resolve(null); },
  get_album_detail: function () { return Promise.resolve(DETAIL); },
  is_favorite: function () { return Promise.resolve(false); },
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); },
  get_album_progress: function () { return Promise.resolve(null); },
  get_download: function () { return Promise.resolve(null); },
  __logCalls: function () { return LOG_CALLS; }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

PROBE = """
setTimeout(function () {
  var out = [];
  function note(text) {
    out.push(text);
    var d = document.getElementById('mark-out');
    if (!d) { d = document.createElement('div'); d.id = 'mark-out'; document.body.appendChild(d); }
    d.textContent = out.join('|');
    try { fetch('/report?d=' + encodeURIComponent(text)); } catch (e) {}
  }
  function kwEl() { return document.querySelector('#keyword'); }
  function cards() { return document.querySelectorAll('.album-list album-card').length; }
  function click(sel, label) {
    var el = document.querySelector(sel);
    if (!el) throw new Error(label + '：找不到 ' + sel);
    el.click();
  }
  var steps = [
    function () { note('boot=' + location.hash); location.hash = '#/search'; },
    function () { note('hashEnterSearch=' + location.hash); },
    function () {
      var input = kwEl();
      if (!input) throw new Error('搜索页没铺出来');
      input.value = 'KW1';
      click('#search-btn', '搜索按钮');
    },
    function () { note('hashAfterSearch=' + location.hash); note('cards=' + cards()); },
    function () { click('.album-list album-card', '第一张卡'); },
    function () {
      note('hashAfterCard=' + location.hash);
      note('hasBack=' + !!document.querySelector('.back-btn'));
      var app = document.querySelector('#app');
      note('appText=' + (app && app.textContent ? app.textContent.replace(/\\s+/g, ' ').slice(0, 100) : '空'));
    },
    function () { click('.back-btn', '详情返回'); },
    function () {
      note('hashAfterBack=' + location.hash);
      note('kwAfterBack=' + (kwEl() ? kwEl().value : 'no-input'));
      note('cardsAfterBack=' + cards());
      note('logCallsAfterBack=' + window.pywebview.api.__logCalls());
    },
    function () {
      var input = kwEl();
      if (input) { input.value = 'KW2'; click('#search-btn', '搜索按钮2'); }
    },
    function () { note('hashAfterSecondSearch=' + location.hash); note('cards2=' + cards()); },
    function () { click('.album-list album-card', '第二张卡'); },
    function () { click('.back-btn', '详情返回2'); },
    function () {
      note('hashAfterSecondBack=' + location.hash);
      note('kwAfterSecondBack=' + (kwEl() ? kwEl().value : 'no-input'));
      note('cardsAfterSecondBack=' + cards());
    },
    function () { history.back(); },
    function () { note('hashAfterLeaveSearch=' + location.hash); note('DONE=1'); }
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
}, 2400);
"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(http.server.SimpleHTTPRequestHandler):
    reports = []

    def do_GET(self):                       # noqa: N802（标准库要求的名字）
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_search_back")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(
        STUB.replace("KW1", KW).replace("KW2", KW2))
    open(os.path.join(tmp, "probe.js"), "w", encoding="utf-8", newline="\n").write(
        PROBE.replace("KW1", KW).replace("KW2", KW2))
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

    profile = os.path.join(tempfile.gettempdir(), "gz_search_back_chrome")
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
    q1 = "#/search?q=" + urllib.parse.quote(KW)
    q2 = "#/search?q=" + urllib.parse.quote(KW2)
    expect = [
        ("搜完地址带关键词", fields.get("hashAfterSearch") == q1),
        ("结果铺出来了", fields.get("cards") == "6"),
        ("点卡片进详情", (fields.get("hashAfterCard") or "").startswith("#/album?id=")),
        ("详情页有返回按钮", fields.get("hasBack") == "true"),
        ("返回回到那次搜索", fields.get("hashAfterBack") == q1),
        ("返回后输入框还是那个词", fields.get("kwAfterBack") == KW),
        ("返回后结果还在", fields.get("cardsAfterBack") == "6"),
        ("返回不算一次新搜索（不刷记录）", fields.get("logCallsAfterBack") == "1"),
        ("换词再搜只改当前这条", fields.get("hashAfterSecondSearch") == q2),
        ("第二次返回也是那次搜索", fields.get("hashAfterSecondBack") == q2),
        ("第二次返回结果还在", fields.get("cardsAfterSecondBack") == "6"),
        ("再返回一次离开搜索页（不堆历史）", fields.get("hashAfterLeaveSearch") == "#/popular"),
    ]
    bad = 0
    for label, ok in expect:
        print("%-4s %s" % ("PASS" if ok else "FAIL", label))
        bad += 0 if ok else 1
    print("ALL PASS" if not bad else "有 %d 条 FAIL" % bad)
    return 0 if not bad else 1


sys.exit(main())