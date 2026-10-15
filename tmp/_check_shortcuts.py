# -*- coding: utf-8 -*-
r"""快捷键面板 + 防社死 + 空状态品牌字标的回归（无头 Chrome + 假桥 + dist 副本）。

盯五件事：
  ① 空状态里的插图是**品牌字标**（`svg.empty-mark`），笔迹和 index.html 闪屏那份一模一样
     （笔数从 index.html 里数出来，不写死 —— 哪天多一笔这里跟着变）；
  ② `?` 唤出快捷键面板，再按 `?` / `Esc` 收起来，面板里三组键位都在；
  ③ `P` 盖住整窗（`.panic-cover` 可见 + `html[data-panic]`），再按 `P` 回来；
     盖住期间别的键被吞（按 `m` 不该有任何反应）；
  ④ 阅读器里按 `P`：自动滚屏**当场停住**（按位移判，不看图标），进度落库；
  ⑤ 在输入框里打 `?` 不该弹面板（不然搜索时用不了问号）。
"""
import http.server
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
function page(n) {
  var c = document.createElement('canvas');
  c.width = 760; c.height = 1400;
  var g = c.getContext('2d');
  g.fillStyle = '#f4f1ea'; g.fillRect(0, 0, 760, 1400);
  g.fillStyle = '#111'; g.font = 'bold 96px sans-serif'; g.fillText('PAGE ' + n, 120, 240);
  return c.toDataURL('image/png');
}
var P1 = page(1), P2 = page(2);
var DETAIL = {
  id: '101', title: '快捷键测试', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 2, cover_url: P1, related: [],
  chapters: [{ photo_id: '9001', index: '1', title: '第 1 话' }]
};
var stub = {
  // 自动滚屏开着（260 px/s）：按 P 之后页面的位移必须停下来
  get_settings: function () {
    return Promise.resolve({ reader: { mode: 'webtoon', auto_scroll: 260, background: 'dark', width: 1080 } });
  },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_favorites: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_search_log: function () { return Promise.resolve([]); },
  log_search: function () { return Promise.resolve(null); },
  save_progress: function () { window.__saved = (window.__saved || 0) + 1; return Promise.resolve(null); },
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
var STEP = 700;
function note(text) { try { fetch('/report?d=' + encodeURIComponent(text)); } catch (e) {} }
function key(name, target) {
  var el = target || window;
  el.dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true }));
}
function panel() { var p = document.querySelector('.hotkey-sheet'); return p && !p.hidden; }
function cover() { var c = document.querySelector('.panic-cover'); return c && !c.hidden; }
function sY() { return Math.round(window.scrollY); }

function phase1() {
  location.hash = '#/search';
  setTimeout(function () {
    var mark = document.querySelector('.empty-art svg.empty-mark');
    note('markCount=' + document.querySelectorAll('.empty-art svg.empty-mark').length);
    note('markPaths=' + (mark ? mark.querySelectorAll('path').length : 0));
    note('markDrawn=' + (mark && (mark.querySelector('path') || {}).getAttribute
      && (mark.querySelector('path').getAttribute('d') || '').length > 20 ? 'yes' : 'no'));
    note('markStroke=' + (mark ? getComputedStyle(mark.querySelector('path')).stroke : 'none'));
    note('panelHiddenAtStart=' + (panel() ? 'no' : 'yes'));

    key('?');
    note('panelAfterQ=' + (panel() ? 'yes' : 'no'));
    note('panelGroups=' + document.querySelectorAll('.hotkey-group').length);
    note('panelRows=' + document.querySelectorAll('.hotkey-row').length);
    key('?');
    note('panelAfterQ2=' + (panel() ? 'yes' : 'no'));
    key('?');
    key('Escape');
    note('panelAfterEsc=' + (panel() ? 'yes' : 'no'));

    key('p');
    note('coverAfterP=' + (cover() ? 'yes' : 'no'));
    note('htmlPanic=' + (document.documentElement.dataset.panic || 'none'));
    key('m');
    note('stillPanicAfterM=' + (cover() ? 'yes' : 'no'));

    var input = document.querySelector('#keyword');
    input.value = 'abc';
    input.focus();
    key('?', input);
    note('panelWhileTyping=' + (panel() ? 'yes' : 'no'));
    input.blur();

    key('p');
    note('coverAfterP2=' + (cover() ? 'no' : 'yes'));
    note('htmlPanic2=' + (document.documentElement.dataset.panic || 'none'));
    setTimeout(phase2, STEP);
  }, 2000);
}

function phase2() {
  window.__saved = 0;
  location.hash = '#/read?photo_id=9001&album_id=101';
  setTimeout(function () {
    note('readerImgs=' + document.querySelectorAll('.reader-images img').length);
    setTimeout(function () {
      var a = sY();
      setTimeout(function () {
        var b = sY();
        note('autoMoved=' + (b > a + 20 ? 'yes' : 'no') + '(' + a + '->' + b + ')');
        key('p');
        note('readerPanic=' + (cover() ? 'yes' : 'no'));
        note('readerSavedOnPanic=' + (window.__saved > 0 ? 'yes' : 'no'));
        setTimeout(function () {
          var c = sY();
          setTimeout(function () {
            var d = sY();
            note('autoStopped=' + (Math.abs(d - c) <= 3 ? 'yes' : 'no') + '(' + c + '->' + d + ')');
            note('DONE=1');
          }, STEP);
        }, 260);
      }, STEP);
    }, 1400);
  }, 1200);
}

setTimeout(phase1, 1600);
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
    index_src = open(os.path.join(REPO, "frontend", "index.html"), encoding="utf-8").read()
    splash_paths = len(re.findall(r"<path pathLength=\"1\"", index_src))

    tmp = os.path.join(tempfile.gettempdir(), "gz_shortcuts")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
    open(os.path.join(tmp, "probe.js"), "w", encoding="utf-8", newline="\n").write(PROBE)
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

    profile = os.path.join(tempfile.gettempdir(), "gz_shortcuts_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=1200,900",
                        "--virtual-time-budget=40000",
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
        ("空状态里是品牌字标（不是 emoji / 方头像）", fields.get("markCount") == "1"),
        ("字标的笔数 = 闪屏那份（%d 笔）" % splash_paths,
         fields.get("markPaths") == str(splash_paths) and splash_paths > 0),
        ("每笔都有真路径数据（d 不为空）", fields.get("markDrawn") == "yes"),
        ("描边走 currentColor（浅深主题都跟得上）",
         (fields.get("markStroke") or "").startswith("rgb(")),
        ("一开始没有面板", fields.get("panelHiddenAtStart") == "yes"),
        ("`?` 唤出面板", fields.get("panelAfterQ") == "yes"),
        ("面板里三组键位", fields.get("panelGroups") == "3"),
        ("键位行都铺出来了（>= 10 行）", int(fields.get("panelRows") or 0) >= 10),
        ("再按 `?` 收起来", fields.get("panelAfterQ2") == "no"),
        ("`Esc` 也能收", fields.get("panelAfterEsc") == "no"),
        ("`P` 盖住整窗", fields.get("coverAfterP") == "yes"),
        ("窗口根上打了 data-panic", fields.get("htmlPanic") == "1"),
        ("盖住期间别的键被吞（按 m 没反应）", fields.get("stillPanicAfterM") == "yes"),
        ("在输入框里打 `?` 不弹面板", fields.get("panelWhileTyping") == "no"),
        ("再按 `P` 收回来", fields.get("coverAfterP2") == "yes"),
        ("data-panic 也清掉了", fields.get("htmlPanic2") == "none"),
        ("阅读器里图铺出来了", fields.get("readerImgs") == "2"),
        ("自动滚屏本来在滚", (fields.get("autoMoved") or "").startswith("yes")),
        ("阅读器里按 P 也盖住", fields.get("readerPanic") == "yes"),
        ("按 P 时把进度落了一次库", fields.get("readerSavedOnPanic") == "yes"),
        ("自动滚屏当场停住（不看图标，看位移）", (fields.get("autoStopped") or "").startswith("yes")),
    ]
    bad = 0
    for label, ok in expect:
        print("%-4s %s" % ("PASS" if ok else "FAIL", label))
        bad += 0 if ok else 1
    print("ALL PASS" if not bad else "有 %d 条 FAIL" % bad)
    return 0 if not bad else 1


sys.exit(main())
