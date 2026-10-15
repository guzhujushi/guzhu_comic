# -*- coding: utf-8 -*-
r"""搜索页「结果太多就先折起来」的回归（无头 Chrome + 假桥 + dist 副本）。

判据：结果多于 FOLD_AT（12）时只铺 12 张 + 一颗「展开其余 N 部」；点开是**追加**铺全、
按钮自己消失；结果本来就不多时不该出现那颗按钮。
"""
import http.server
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
KW_MANY = "FOLD"
KW_FEW = "SMALL"

STUB = """
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  // 一次给 30 部（图源一页就是这个量级）；换个小词只给 6 部
  search: function (keyword) {
    var n = keyword === 'KWMANY' ? 30 : 6;
    var out = [];
    for (var i = 1; i <= n; i++) out.push({ id: '10' + i, title: '测试用漫画 ' + i, cover_url: '', favorited: false });
    return Promise.resolve(out);
  },
  get_search_log: function () { return Promise.resolve([]); },
  log_search: function () { return Promise.resolve(null); },
  get_album_detail: function () { return Promise.resolve(null); },
  is_favorite: function () { return Promise.resolve(false); },
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); },
  get_album_progress: function () { return Promise.resolve(null); },
  get_download: function () { return Promise.resolve(null); }
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
  function cards() { return document.querySelectorAll('.album-list album-card').length; }
  function more() { return document.querySelector('.search-more'); }
  function search(word) {
    var input = document.querySelector('#keyword');
    input.value = word;
    document.querySelector('#search-btn').click();
  }
  location.hash = '#/search';
  setTimeout(function () {
    search('KWMANY');
    setTimeout(function () {
      note('cardsMany=' + cards());
      note('moreText=' + (more() ? more().textContent : 'none'));
      note('moreCards=' + document.querySelectorAll('.search-more').length);
      if (more()) more().click();
      setTimeout(function () {
        note('cardsExpanded=' + cards());
        note('moreAfterClick=' + (more() ? 'still' : 'gone'));
        // 展开之后地址不该被改（换词才算新搜索）
        note('hashAfterExpand=' + location.hash);
        search('KWFEW');
        setTimeout(function () {
          note('cardsFew=' + cards());
          note('moreOnFew=' + (more() ? 'yes' : 'no'));
          note('DONE=1');
        }, 1500);
      }, 1200);
    }, 1800);
  }, 1500);
}, 2200);
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_search_fold")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(
        STUB.replace("KWMANY", KW_MANY).replace("KWFEW", KW_FEW))
    open(os.path.join(tmp, "probe.js"), "w", encoding="utf-8", newline="\n").write(
        PROBE.replace("KWMANY", KW_MANY).replace("KWFEW", KW_FEW))
    idx = os.path.join(tmp, "index.html")
    page = open(idx, encoding="utf-8").read().replace(
        "</head>", '<script src="/stub.js"></script></head>', 1)
    open(idx, "w", encoding="utf-8", newline="").write(
        page.replace("</body>", '<script src="/probe.js"></script></body>', 1))

    port = free_port()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.directory = tmp
    os.chdir(tmp)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_search_fold_chrome")
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
        ("结果 30 部时先只铺 12 张", fields.get("cardsMany") == "12"),
        ("有一颗展开按钮", fields.get("moreCards") == "1"),
        ("按钮写明还剩几部", "展开其余 18 部" in (fields.get("moreText") or "")),
        ("点开后把剩下的都铺出来（追加，不重建）", fields.get("cardsExpanded") == "30"),
        ("展开后按钮自己消失", fields.get("moreAfterClick") == "gone"),
        ("展开不改地址栏（不算新搜索）", (fields.get("hashAfterExpand") or "").startswith("#/search")),
        ("结果只有 6 部时全铺出来", fields.get("cardsFew") == "6"),
        ("结果不多就没有那颗按钮", fields.get("moreOnFew") == "no"),
    ]
    bad = 0
    for label, ok in expect:
        print("%-4s %s" % ("PASS" if ok else "FAIL", label))
        bad += 0 if ok else 1
    print("ALL PASS" if not bad else "有 %d 条 FAIL" % bad)
    return 0 if not bad else 1


sys.exit(main())