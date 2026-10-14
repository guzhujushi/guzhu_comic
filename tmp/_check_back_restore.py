# -*- coding: utf-8 -*-
"""「返回还原」的回归：滚动位置 + 分类页 / 论坛的页码。

用户报过的两条路都在里面：
  A) 搜索 → 点卡进详情 → 返回：落回刚才那次搜索，而且滚动位置也回去
  B) 分类页 / 论坛翻了页 → 进详情 → 返回：页码和列表都还在
另外顺手测了对照面：点导航栏进新页面（不是"退回来"）不该被还原成旧位置。
"""
import http.server, os, shutil, socket, subprocess, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
function albums(page, n) {
  var out = [];
  for (var i = 0; i < n; i++) {
    out.push({ id: 'p' + page + 'a' + i, title: 'P' + page + '-' + i, cover_url: '', favorited: false });
  }
  return out;
}
var DETAIL = {
  id: 'x', title: '详情', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 1, cover_url: '', related: [],
  chapters: [{ photo_id: '9001', index: '1', title: '第 1 话' }]
};
var RANK_CALLS = [];
var forum = function (page) {
  var items = [];
  for (var i = 0; i < 5; i++) {
    items.push({ comment_id: 'c' + page + i, nickname: '路人' + i, content: '第' + page + '页第' + i + '条',
                 created_at: '2026-01-01', spoiler: false, reply: '', reply_count: 0,
                 album_id: 'f' + page + i, favorited: false });
  }
  return { total: 100, has_more: true, items: items };
};
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function (range, category, page, sort) {
    RANK_CALLS.push(category + '/' + page);
    return Promise.resolve(albums(page, 12));
  },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_album_detail: function () { return Promise.resolve(DETAIL); },
  get_album_titles: function () { return Promise.resolve({}); },
  get_search_log: function () { return Promise.resolve([]); },
  log_search: function () { return Promise.resolve(null); },
  search: function () { return Promise.resolve(albums(1, 20)); },
  get_forum: function (page) { return Promise.resolve(forum(page)); },
  is_favorite: function () { return Promise.resolve(false); },
  get_album_progress: function () { return Promise.resolve(null); },
  get_download: function () { return Promise.resolve(null); },
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); },
  __rank: function () { return RANK_CALLS.join(','); }
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
  function y() { return Math.round(window.scrollY); }
  function cards() { return document.querySelectorAll('.board-panel album-card').length; }
  function searchCards() { return document.querySelectorAll('.search-page album-card').length; }
  function forumItems() { return document.querySelectorAll('.forum-list .comment').length; }
  function click(sel, label) {
    var el = document.querySelector(sel);
    if (!el) throw new Error(label + '找不到 ' + sel);
    el.click();
  }
  function nav(path, label) {
    var el = document.querySelector('#nav a[data-path="' + path + '"]');
    if (!el) throw new Error(label + '找不到导航 ' + path);
    el.click();
  }
  var steps = [
    // ---------- A：搜索 → 详情 → 返回 ----------
    function () { nav('/popular', '热门'); },
    function () { window.scrollTo(0, 400); note('popularScroll=' + y()); },
    function () { nav('/search', '搜索'); },
    function () {
      note('hashSearch=' + location.hash);
      var input = document.querySelector('#keyword');
      if (!input) throw new Error('搜索页没播出来');
      input.value = '测试';
      click('#search-btn', '搜索按钮');
    },
    function () { note('cardsAfterSearch=' + searchCards()); window.scrollTo(0, 500); note('searchScroll=' + y()); },
    function () { click('.search-page album-card', '第一张结果'); note('hashAfterCard=' + location.hash); },
    function () { click('.back-btn', '详情返回'); },
    function () { }, function () { }, function () {
      note('hashAfterBack=' + location.hash);
      note('scrollAfterBack=' + y());
      note('cardsAfterBack=' + searchCards());
    },

    // ---------- 对照面：点导航进新页面，不该把旧位置搬过来 ----------
    function () { nav('/popular', '热门'); },
    function () { }, function () { note('scrollAfterNav=' + y()); },
    function () { history.back(); },
    function () { }, function () { note('scrollAfterBack2=' + y()); },

    // ---------- B：分类页页码 ----------
    function () { location.hash = '#/category?c=doujin'; },
    function () { note('hashCatBoot=' + location.hash); note('catCards=' + cards()); },
    function () { click('.load-more button', '加载更多'); },
    function () { click('.load-more button', '加载更多 2'); },
    function () {
      note('hashCatPaged=' + location.hash);
      note('catCardsPaged=' + cards());
      window.scrollTo(0, 600);
      note('catScroll=' + y());
    },
    function () { click('.board-panel album-card', '第一张分类卡'); note('hashCatCard=' + location.hash); },
    function () { click('.back-btn', '详情返回'); },
    function () { }, function () { }, function () {
      note('hashCatBack=' + location.hash);
      note('catCardsBack=' + cards());
      note('catScrollBack=' + y());
      note('rankCalls=' + window.pywebview.api.__rank());
    },

    // ---------- C：论坛页码 ----------
    function () { location.hash = '#/forum'; },
    function () { click('.forum-more', '论坛加载更多'); },
    function () {
      note('hashForum=' + location.hash);
      note('forumItems=' + forumItems());
      window.scrollTo(0, 500);
      note('forumScroll=' + y());
    },
    function () { click('.forum-list .forum-album', '论坛封面条'); note('hashForumCard=' + location.hash); },
    function () { click('.back-btn', '详情返回'); },
    function () { }, function () { }, function () {
      note('hashForumBack=' + location.hash);
      note('forumItemsBack=' + forumItems());
      note('forumScrollBack=' + y());
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_back_restore")
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

    profile = os.path.join(tempfile.gettempdir(), "gz_back_restore_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=1200,900",
                        "--virtual-time-budget=90000",
                        "http://127.0.0.1:%d/#/popular" % port],
                       capture_output=True, timeout=600)
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

    def near(key, want, tol=6):
        try:
            return abs(int(fields.get(key, "-1")) - want) <= tol
        except ValueError:
            return False

    q = urllib.parse.quote("测试")
    expect = [
        ("搜完地址带关键词", (fields.get("hashSearch") or "") == "#/search"),
        ("结果铺出来了（20 张）", fields.get("cardsAfterSearch") == "20"),
        ("返回落回那次搜索", (fields.get("hashAfterBack") or "") == "#/search?q=" + q),
        ("返回后结果还在", fields.get("cardsAfterBack") == "20"),
        ("返回后滚动位置也回来了", near("scrollAfterBack", 500)),
        ("点导航进新页面回到顶部（不是接着上一页的位置）", near("scrollAfterNav", 0, 4)),
        ("再从新页面退回搜索页也会还原", near("scrollAfterBack2", 500)),
        ("分类页首屏照常", (fields.get("hashCatBoot") or "") == "#/category?c=doujin"),
        ("翻两页后页码进地址", (fields.get("hashCatPaged") or "") == "#/category?c=doujin&page=3"),
        ("翻页确实多铺了卡（12×3-3=33）", fields.get("catCardsPaged") == "33"),
        ("返回落回第 3 页", (fields.get("hashCatBack") or "") == "#/category?c=doujin&page=3"),
        ("返回后列表还是 33 张", fields.get("catCardsBack") == "33"),
        ("返回后滚动位置也回来了", near("catScrollBack", 600)),
        ("返回时按顺序把前三页补齐（首进 + 返回各一轮）",
         (fields.get("rankCalls") or "").count("doujin/1,doujin/2,doujin/3") == 2),
        ("论坛翻页后页码进地址", (fields.get("hashForum") or "") == "#/forum?page=2"),
        ("论坛铺了两页（10 条）", fields.get("forumItems") == "10"),
        ("论坛返回落回第 2 页", (fields.get("hashForumBack") or "") == "#/forum?page=2"),
        ("论坛返回后还是 10 条", fields.get("forumItemsBack") == "10"),
        ("论坛返回后滚动位置也回来了", near("forumScrollBack", 500)),
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
