# -*- coding: utf-8 -*-
r"""搜索页「输入联想」的回归（无头 Chrome + 假桥 + dist 副本）。

联想的词只能来自本机：最近搜索（`search_log`）+ 收藏 / 看过的标题。这一支盯：
  ① 打一个字就出建议，来源（最近 / 收藏 / 看过）标对；
  ② `↓` 选中、回车**采用选中的那条**（而不是搜输入框里的字）；
  ③ 不选直接回车 = 搜原样的词，并且面板收起来（结果铺出来之后不该还挂着）；
  ④ `Esc` 收起；没命中的词没有面板。
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

STUB = """
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_search_log: function () {
    return Promise.resolve([
      { keyword: '火影', count: 3, at: 2 }, { keyword: '海贼', count: 1, at: 1 }
    ]);
  },
  get_favorites: function () {
    return Promise.resolve([{ album_id: '1', title: '火影忍者 同人集', cover_url: '', added_at: 1, favorited: true }]);
  },
  get_history: function () {
    return Promise.resolve([{ album_id: '2', photo_id: '9', page_index: 3, title: '海贼王 剧场版', cover_url: '', updated_at: 1 }]);
  },
  search: function (keyword) {
    window.__last = keyword;
    window.__calls = (window.__calls || 0) + 1;
    return Promise.resolve([{ id: '10', title: '结果 ' + keyword, cover_url: '', favorited: false }]);
  },
  log_search: function () { return Promise.resolve(null); }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

PROBE = """
var STEP = 600;
function note(text) { try { fetch('/report?d=' + encodeURIComponent(text)); } catch (e) {} }
function panel() { var p = document.querySelector('.search-suggest'); return p && !p.hidden; }
function rows() {
  return [].map.call(document.querySelectorAll('.suggest-row'), function (r) {
    return r.querySelector('.suggest-word').textContent + '/' + r.querySelector('.suggest-kind').textContent;
  }).join(',');
}
function type(text) {
  var input = document.querySelector('#keyword');
  input.value = text;
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
function press(name) {
  document.querySelector('#keyword').dispatchEvent(
    new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true }));
}
function resultTitle() {
  var c = document.querySelector('.album-list album-card p');
  return c ? c.textContent : 'none';
}

setTimeout(function () {
  location.hash = '#/search';
  setTimeout(function () {
    note('insideWrap=' + (document.querySelector('.search-input-wrap .search-suggest') ? 'yes' : 'no'));
    note('hiddenAtStart=' + (panel() ? 'no' : 'yes'));
    note('coldRows=' + (panel() ? rows() : 'none'));

    type('火');
    setTimeout(function () {
      note('firePanel=' + (panel() ? 'yes' : 'no'));
      note('fireRows=' + rows());

      type('海');
      setTimeout(function () {
        note('seaRows=' + rows());

        // ↓ 选中第二条（最近搜索那条排最前，第二条是"看过"的标题），回车采用它
        type('海');
        press('ArrowDown');
        press('ArrowDown');
        note('activeRows=' + [].map.call(document.querySelectorAll('.suggest-row'),
          function (r) { return r.classList.contains('on') ? '1' : '0'; }).join(''));
        press('Enter');
        setTimeout(function () {
          note('picked=' + (window.__last || 'none'));
          note('panelAfterPick=' + (panel() ? 'yes' : 'no'));

          // 不选直接回车：搜输入框里原样的词
          type('火影');
          press('Enter');
          setTimeout(function () {
            note('typed=' + (window.__last || 'none'));
            note('panelAfterEnter=' + (panel() ? 'yes' : 'no'));
            note('result=' + resultTitle());

            // 没命中的词：面板整块收起来
            type('zzz');
            setTimeout(function () {
              note('noMatch=' + (panel() ? 'yes' : 'no'));
              // Esc 收起
              type('火');
              setTimeout(function () {
                note('fireAgain=' + (panel() ? 'yes' : 'no'));
                press('Escape');
                note('afterEsc=' + (panel() ? 'yes' : 'no'));
                note('DONE=1');
              }, STEP);
            }, STEP);
          }, STEP);
        }, STEP);
      }, STEP);
    }, STEP);
  }, 2000);
}, 1600);
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_search_suggest")
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

    profile = os.path.join(tempfile.gettempdir(), "gz_search_suggest_chrome")
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
    fire = fields.get("fireRows") or ""
    sea = fields.get("seaRows") or ""
    expect = [
        ("面板挂在输入框下面（.search-input-wrap 里）", fields.get("insideWrap") == "yes"),
        ("没打字时面板是收着的", fields.get("hiddenAtStart") == "yes"),
        ("打「火」出面板", fields.get("firePanel") == "yes"),
        ("命中最近搜索「火影」并标「最近」", "火影/最近" in fire),
        ("命中收藏标题并标「收藏」", "火影忍者 同人集/收藏" in fire),
        ("打「海」命中「看过」的标题", "海贼王 剧场版/看过" in sea),
        ("最近搜索那条排在最前", sea.startswith("海贼/最近")),
        ("↓ 选中第二条", fields.get("activeRows") == "01"),
        ("回车采用选中的那条（不是输入框里的字）", fields.get("picked") == "海贼王 剧场版"),
        ("采用后面板收起来", fields.get("panelAfterPick") == "no"),
        ("不选直接回车 = 搜原样的词", fields.get("typed") == "火影"),
        ("结果铺出来后联想面板不挂着了", fields.get("panelAfterEnter") == "no"),
        ("搜出来的结果真的铺上了", fields.get("result") == "结果 火影"),
        ("没命中的词不弹面板", fields.get("noMatch") == "no"),
        ("再打「火」面板回来", fields.get("fireAgain") == "yes"),
        ("Esc 收起面板", fields.get("afterEsc") == "no"),
    ]
    bad = 0
    for label, ok in expect:
        print("%-4s %s" % ("PASS" if ok else "FAIL", label))
        bad += 0 if ok else 1
    print("ALL PASS" if not bad else "有 %d 条 FAIL" % bad)
    return 0 if not bad else 1


sys.exit(main())
