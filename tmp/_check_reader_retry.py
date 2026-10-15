# -*- coding: utf-8 -*-
r"""阅读器「图没下来」这条路的回归（无头 Chrome + 假桥 + dist 副本）。

三件事一起咬住（都是 2026-10-15 用户报的"安卓上网络不好图不出来、整本下完也不出来"）：

  ① **重试必须保住 token**：打包态 / 安卓的图片 URL 上带 `?t=<token>`，重试时如果拼成
     `?t=TOKEN?r=1`，服务端会把 token 解析成 `TOKEN?r=1` → 每次重试都 403，一张图首帧没下来
     就永远补不回来。假服务照真服务那套解析 token（`parse_qs`），第一帧故意 404、之后才放行。
  ② **手动刷新**：顶栏那颗刷新按钮点一下要重新问一次 `get_chapter`。
  ③ **下载下完自动刷新**：还有破图时盯着 `get_download`，从"在下"变"下完"就重拉本话 ——
     整本下载落在 download.dir（`/downloads/…`），而阅读器手里那批是 `/images/…`。

判据：破图数（`img[data-broken="true"]`）、自然高度（`naturalHeight > 0`）、以及假服务的请求计数。
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
TOKEN = "TOK-abc123"

# 1x1 的合法 PNG（够让 naturalHeight > 0）
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d4944415478da63f8cfc0f01f00050101002ab394"
    "210000000049454e44ae426082"
)

STUB = """
var TOKEN = '__TOKEN__';
var IMG = 'http://127.0.0.1:__PORT__/img/';
var DL = 'http://127.0.0.1:__PORT__/dl/';
var CHAPTER_CALLS = 0;
var DL_CALLS = 0;
function urls() {
  // 第 1 次：a 第一帧失败（模拟"还没下下来"）、b 正常
  if (CHAPTER_CALLS === 1) return [IMG + 'a.png?t=' + TOKEN, IMG + 'b.png?t=' + TOKEN];
  // 第 2 次（手点刷新）：多一张永远拿不到的图，好让"还有破图"这条成立
  if (CHAPTER_CALLS === 2) return [IMG + 'a.png?t=' + TOKEN, IMG + 'b.png?t=' + TOKEN, IMG + 'gone.png?t=' + TOKEN];
  // 第 3 次（下载下完自动刷）：换成离线副本那一套（与真后端 get_chapter 的口径一致）
  return [DL + 'a.png?t=' + TOKEN, DL + 'b.png?t=' + TOKEN, DL + 'c.png?t=' + TOKEN];
}
var stub = {
  get_settings: function () { return Promise.resolve({ reader: { mode: 'webtoon', background: 'dark', width: 1080 } }); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_album_detail: function () { return Promise.resolve(DETAIL); },
  get_chapter: function () { CHAPTER_CALLS += 1; return Promise.resolve({ photo_id: '9001', images: urls() }); },
  get_progress: function () { return Promise.resolve(0); },
  save_progress: function () { return Promise.resolve(null); },
  is_favorite: function () { return Promise.resolve(false); },
  get_album_progress: function () { return Promise.resolve(null); },
  // 前两次"在下"，第三次起"下完了"（整本只 2 话）
  get_download: function () {
    DL_CALLS += 1;
    return Promise.resolve(DL_CALLS < 3
      ? { album_id: '101', state: 'running', running: true, total: 2, done: 1 }
      : { album_id: '101', state: 'done', running: false, total: 2, done: 2 });
  },
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); },
  __chapterCalls: function () { return CHAPTER_CALLS; },
  __dlCalls: function () { return DL_CALLS; }
};
var DETAIL = {
  id: '101', title: '容错测试', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 3, cover_url: '', related: [],
  chapters: [{ photo_id: '9001', index: '1', title: '第 1 话' }, { photo_id: '9002', index: '2', title: '第 2 话' }]
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
  function imgs() { return [].slice.call(document.querySelectorAll('.reader-images img')); }
  function broken() { return document.querySelectorAll('.reader-images img[data-broken="true"]').length; }
  function loaded() { return imgs().filter(function (i) { return i.naturalHeight > 0; }).length; }
  function sample(tag) {
    note(tag + '_imgs=' + imgs().length);
    note(tag + '_broken=' + broken());
    note(tag + '_loaded=' + loaded());
  }
  function calls() { return window.pywebview.api.__chapterCalls(); }

  location.hash = '#/read?photo_id=9001&album_id=101';
  setTimeout(function () {
    note('hasRefresh=' + !!document.querySelector('.reader-top .refresh-btn'));
    // 覆盖第一次重试（快档 2 秒）：带对 token 才补得回来
    setTimeout(function () {
      sample('retry');
      document.querySelector('.reader-top .refresh-btn').click();
      setTimeout(function () {
        sample('refresh');
        note('callsAfterRefresh=' + calls());
        // 等"下载下完自动刷"：那只表 5 秒一档，等到重新拉过本话为止（最多 25 秒）
        var waited = 0;
        (function wait() {
          if (calls() >= 3 || waited >= 25000) {
            setTimeout(function () {
              sample('auto');
              note('srcKinds=' + imgs().map(function (i) {
                return i.src.indexOf('/dl/') >= 0 ? 'dl' : 'img';
              }).join(','));
              note('toast=' + document.querySelector('.reader-toast').textContent);
              note('callsEnd=' + calls());
              note('dlCalls=' + window.pywebview.api.__dlCalls());
              note('waited=' + waited);
              note('DONE=1');
            }, 2500);
            return;
          }
          waited += 500;
          setTimeout(wait, 500);
        })();
      }, 2500);
    }, 4000);
  }, 1500);
}, 2500);
"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(http.server.SimpleHTTPRequestHandler):
    reports = []
    hits = {}
    notfound = {}
    bad_token = 0

    def do_GET(self):                       # noqa: N802（标准库要求的名字）
        path = urllib.parse.urlparse(self.path).path
        if self.path.startswith("/report?"):
            query = urllib.parse.urlparse(self.path).query
            Handler.reports.append(urllib.parse.parse_qs(query).get("d", [""])[0])
            self.send_response(204)
            self.end_headers()
            return
        if path.startswith("/img/") or path.startswith("/dl/"):
            self.image(path)
            return
        super().do_GET()

    def image(self, path):
        """照真服务那套取 token：`?t=` 被拼坏了（`?t=TOKEN?r=1`）就取不到 → 403"""
        name = path.rsplit("/", 1)[-1]
        token = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("t") or [None])[0]
        if token != TOKEN:
            Handler.bad_token += 1
            self.send_error(403, "Forbidden token")
            return
        Handler.hits[name] = Handler.hits.get(name, 0) + 1
        if name == "gone.png" or (name == "a.png" and Handler.hits[name] == 1):
            Handler.notfound[name] = Handler.notfound.get(name, 0) + 1
            self.send_error(404, "Not Found")      # 第一帧故意不给：模拟"图还没下下来"
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(PNG)))
        self.end_headers()
        self.wfile.write(PNG)

    def log_message(self, *args):
        pass


def main():
    Handler.reports = []
    Handler.hits = {}
    Handler.notfound = {}
    Handler.bad_token = 0

    tmp = os.path.join(tempfile.gettempdir(), "gz_reader_retry")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)

    port = free_port()
    stub = STUB.replace("__TOKEN__", TOKEN).replace("__PORT__", str(port))
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(stub)
    open(os.path.join(tmp, "probe.js"), "w", encoding="utf-8", newline="\n").write(PROBE)
    idx = os.path.join(tmp, "index.html")
    page = open(idx, encoding="utf-8").read().replace(
        "</head>", '<script src="/stub.js"></script></head>', 1)
    open(idx, "w", encoding="utf-8", newline="").write(
        page.replace("</body>", '<script src="/probe.js"></script></body>', 1))

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.directory = tmp
    os.chdir(tmp)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_reader_retry_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=1200,900",
                        "--virtual-time-budget=60000",
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
    print("图片请求 %s；404 %s；token 被拒 %d 次" % (Handler.hits, Handler.notfound, Handler.bad_token))
    shutil.rmtree(tmp, ignore_errors=True)

    if "DONE" not in fields:
        print("FAIL 探针没跑完（上面那条就是走到哪儿）")
        return 1
    expect = [
        ("阅读器铺了 2 张图", fields.get("retry_imgs") == "2"),
        ("顶栏有刷新按钮", fields.get("hasRefresh") == "true"),
        ("a 的第一帧确实 404 过一次（「图还没下下来」那条路真的走到）", Handler.notfound.get("a.png") == 1),
        ("重试把缺的那张补回来了（token 没被 ?r= 拼坏）", fields.get("retry_broken") == "0"),
        ("重试后两张都真解码出来了", fields.get("retry_loaded") == "2"),
        ("a 被重新请求过（确实走了重试，不是没试）", Handler.hits.get("a.png", 0) >= 2),
        ("点刷新重新问了后端", fields.get("callsAfterRefresh") == "2"),
        ("刷新后按新列表铺 3 张", fields.get("refresh_imgs") == "3"),
        ("刷新后仍有 1 张破图（那张永远拿不到）", fields.get("refresh_broken") == "1"),
        ("下载下完后自动重拉：换成离线副本那套 URL", fields.get("srcKinds") == "dl,dl,dl"),
        ("自动重拉后 3 张都解码出来了", fields.get("auto_loaded") == "3"),
        ("自动重拉后没有破图", fields.get("auto_broken") == "0"),
        ("自动重拉带一句提示", "下载完成" in (fields.get("toast") or "")),
        ("一共问了后端 3 次章节（进页面 / 手刷 / 自动刷）", fields.get("callsEnd") == "3"),
        ("盯下载那只表读到过「在下」（不是一次就断言下完）", int(fields.get("dlCalls") or 0) >= 3),
        ("全程没有被 token 拦掉一次请求", Handler.bad_token == 0),
    ]
    bad = 0
    for label, ok in expect:
        print("%-4s %s" % ("PASS" if ok else "FAIL", label))
        bad += 0 if ok else 1
    print("ALL PASS" if not bad else "有 %d 条 FAIL" % bad)
    return 0 if not bad else 1


sys.exit(main())