# -*- coding: utf-8 -*-
r"""阅读器触屏手势的回归（无头 Chrome + 假桥 + dist 副本）。

盯这几条（都是"手机上有、桌面上靠键盘 / 鼠标顶上"的那批能力）：
  ① 左右滑翻页（等价 ←/→）；斜着划拉 / 划得太短不算翻页；
  ② 滑完浏览器补的那一下 click 不算数（否则一次滑动会翻两页）；
  ③ 从左 / 右边缘横滑切上一话 / 下一话；
  ④ 中间双击放大到两倍宽、再双击还原；左右两侧双击**不**放大（那两块的单击是翻页）。
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
  id: '101', title: '手势测试', author: '作者', authors: ['作者'], description: '简介',
  tags: [], likes: '1', views: '2', comment_count: '0', pub_date: '', update_date: '',
  page_count: 2, cover_url: P1, related: [],
  chapters: [{ photo_id: '9001', index: '1', title: '第 1 话' }, { photo_id: '9002', index: '2', title: '第 2 话' }]
};
var stub = {
  get_settings: function () {
    return Promise.resolve({ reader: { mode: 'single', background: 'dark', width: 1080, click_to_page: true } });
  },
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
  get_comments: function () { return Promise.resolve({ total: 0, has_more: false, items: [] }); },
  save_progress: function () { return Promise.resolve(null); }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

PROBE = """
var STEP = 500;
function note(text) { try { fetch('/report?d=' + encodeURIComponent(text)); } catch (e) {} }
function label() {
  var el = document.querySelector('.reader-page');
  return el ? el.textContent : 'none';
}
function hashChapter() {
  var m = /photo_id=(\\d+)/.exec(location.hash);
  return m ? m[1] : 'none';
}
function touch(kind, x, y) {
  var target = document.querySelector('.reader-images') || document.body;
  var t = new Touch({ identifier: 1, target: target, clientX: x, clientY: y });
  var ev = new TouchEvent(kind, {
    touches: kind === 'touchend' ? [] : [t],
    changedTouches: [t], targetTouches: [], bubbles: true, cancelable: true
  });
  target.dispatchEvent(ev);
}
function swipe(x1, y1, x2, y2) { touch('touchstart', x1, y1); touch('touchend', x2, y2); }
function click(x) {
  document.querySelector('.reader-images').dispatchEvent(
    new MouseEvent('click', { clientX: x, clientY: 500, bubbles: true }));
}
function zoomed() { return document.querySelector('.reader').classList.contains('zoomed'); }
function col() { return document.querySelector('.reader').style.getPropertyValue('--reader-col'); }

setTimeout(function () {
  location.hash = '#/read?photo_id=9001&album_id=101';
  setTimeout(function () {
    var W = window.innerWidth, H = window.innerHeight;
    var midY = Math.round(H / 2);
    note('start=' + label() + ',' + hashChapter() + ',imgs=' +
      document.querySelectorAll('.reader-images img').length);

    swipe(W - 200, midY, 200, midY);                  // 往左滑 = 下一页
    note('afterLeftSwipe=' + label());
    click(200);                                       // 滑完补的那一下 click：不许再翻一次
    note('afterTrailingClick=' + label());
    swipe(200, midY, W - 200, midY);                  // 往右滑 = 上一页
    note('afterRightSwipe=' + label());
    swipe(W - 200, midY, 200, midY - 400);            // 斜着划拉：不算翻页
    note('afterDiagonal=' + label());
    swipe(W - 200, midY, W - 230, midY);              // 划得太短：不算翻页
    note('afterTinySwipe=' + label());

    swipe(8, midY, W - 120, midY);                    // 左边缘往右滑：上一话（没有上一话，原地不动）
    note('afterLeftEdge=' + hashChapter());
    swipe(W - 8, midY, 120, midY);                    // 右边缘往左滑：下一话
    setTimeout(function () {
      note('afterRightEdge=' + hashChapter());

      // 中间双击：放大 → 还原
      var cx = Math.round(W / 2), cy = midY;
      touch('touchstart', cx, cy); touch('touchend', cx, cy);
      touch('touchstart', cx, cy); touch('touchend', cx, cy);
      note('zoomOn=' + (zoomed() ? 'yes' : 'no') + ',col=' + col());
      touch('touchstart', cx, cy); touch('touchend', cx, cy);
      touch('touchstart', cx, cy); touch('touchend', cx, cy);
      note('zoomOff=' + (zoomed() ? 'yes' : 'no') + ',col=' + col());

      // 左右两侧双击：那是翻页区，不许放大
      touch('touchstart', 60, cy); touch('touchend', 60, cy);
      touch('touchstart', 60, cy); touch('touchend', 60, cy);
      note('zoomOnEdge=' + (zoomed() ? 'yes' : 'no'));
      note('DONE=1');
    }, 1600);
  }, 2400);
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
    tmp = os.path.join(tempfile.gettempdir(), "gz_reader_gesture")
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

    profile = os.path.join(tempfile.gettempdir(), "gz_reader_gesture_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=420,860",
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
    zoom_on = fields.get("zoomOn") or ""
    zoom_off = fields.get("zoomOff") or ""
    expect = [
        ("进页面在第 1 话第 1 页（窗口按手机尺寸给）", fields.get("start") == "1 / 2,9001,imgs=2"),
        ("往左滑 = 下一页", fields.get("afterLeftSwipe") == "2 / 2"),
        ("滑完补的那一下 click 不再翻一次", fields.get("afterTrailingClick") == "2 / 2"),
        ("往右滑 = 上一页", fields.get("afterRightSwipe") == "1 / 2"),
        ("斜着划拉不翻页", fields.get("afterDiagonal") == "1 / 2"),
        ("划得太短不翻页", fields.get("afterTinySwipe") == "1 / 2"),
        ("左边缘往右滑：没有上一话就原地不动", fields.get("afterLeftEdge") == "9001"),
        ("右边缘往左滑 = 下一话", fields.get("afterRightEdge") == "9002"),
        ("中间双击放大", zoom_on.startswith("yes")),
        ("放大用的是两倍宽", zoom_on.endswith("col=200%")),
        ("再双击还原", zoom_off.startswith("no")),
        ("还原回设置里那档宽度（1080px）", zoom_off.endswith("col=1080px")),
        ("左右两侧双击不放大（那块是翻页区）", fields.get("zoomOnEdge") == "no"),
    ]
    bad = 0
    for label, ok in expect:
        print("%-4s %s" % ("PASS" if ok else "FAIL", label))
        bad += 0 if ok else 1
    print("ALL PASS" if not bad else "有 %d 条 FAIL" % bad)
    return 0 if not bad else 1


sys.exit(main())
