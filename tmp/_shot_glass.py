# -*- coding: utf-8 -*-
import functools, http.server, os, shutil, socket, subprocess, sys, tempfile, threading

REPO = r"D:\guzhu_comic"
OUT = os.path.join(REPO, "tmp", "_ui")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
function page(n, color) {
  var c = document.createElement('canvas');
  c.width = 760; c.height = 1100;
  var g = c.getContext('2d');
  g.fillStyle = '#f4f1ea'; g.fillRect(0, 0, 760, 1100);
  g.strokeStyle = color; g.lineWidth = 6;
  for (var y = 40; y < 1100; y += 46) { g.beginPath(); g.moveTo(40, y); g.lineTo(720, y); g.stroke(); }
  g.fillStyle = '#111'; g.font = 'bold 96px sans-serif';
  g.fillText('PAGE ' + n, 120, 240);
  g.font = 'bold 40px sans-serif';
  g.fillText('manga content', 120, 320);
  return c.toDataURL('image/png');
}
var P1 = page(1, '#c0392b'), P2 = page(2, '#2c6fb5'), P3 = page(3, '#2f8f5b');
var DETAIL = {
  id: '101', title: '玻璃测试漫画', author: '作者', authors: ['作者'],
  description: '简介：这里是一段很长的简介文字，用来看看它下面有没有毛玻璃。',
  tags: ['标签A', '标签B'], likes: '12', views: '345', comment_count: '7',
  pub_date: '2026-01-01', update_date: '2026-02-02', page_count: 3, cover_url: P1,
  related: [{ id: '201', title: '相关作品甲', author: '作者甲', cover_url: P2 }],
  chapters: [
    { photo_id: '9001', index: '1', title: '第 1 话' },
    { photo_id: '9002', index: '2', title: '第 2 话' }
  ]
};
var SETTINGS = { reader: { mode: 'MODE', background: 'dark', width: 1080 } };
var stub = {
  get_settings: function () { return Promise.resolve(SETTINGS); },
  prefetch_home: function () { return Promise.resolve(0); },
  prefetch_albums: function () { return Promise.resolve(0); },
  prefetch_chapter: function () { return Promise.resolve(0); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); },
  get_album_detail: function () { return Promise.resolve(DETAIL); },
  get_chapter: function () { return Promise.resolve({ images: [P1, P2, P3] }); },
  get_progress: function () { return Promise.resolve(0); },
  is_favorite: function () { return Promise.resolve(false); },
  get_album_progress: function () { return Promise.resolve(null); },
  get_download: function () { return Promise.resolve(null); },
  get_comments: function () { return Promise.resolve({ total: 1, has_more: false, items: [
    { nickname: '路人', content: '评论内容', created_at: '2026-01-01', spoiler: false, reply: '' }] }); }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

BARS = ("setInterval(function(){"
        "document.querySelectorAll('.reader-top,.reader-dock')"
        ".forEach(function(e){e.dataset.visible='true';});},30);")
CLICK = ("setTimeout(function(){var b=document.querySelector('%s'); if(b) b.click();},1200);")

SHOTS = [
    ("reader-webtoon", "#/read?photo_id=9001&album_id=101", 6000, BARS, "webtoon"),
    ("reader-single", "#/read?photo_id=9001&album_id=101", 6000, BARS, "single"),
    ("reader-chapters", "#/read?photo_id=9001&album_id=101", 6000, BARS + CLICK % ".chapters-btn", "webtoon"),
    ("reader-settings", "#/read?photo_id=9001&album_id=101", 6000, BARS + CLICK % ".settings-btn", "single"),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(tempfile.gettempdir(), "gz_glass")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    idx = os.path.join(tmp, "index.html")
    base = open(idx, encoding="utf-8").read()

    port = free_port()
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
    httpd.log_message = lambda *a: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_glass_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    url = "http://127.0.0.1:%d/" % port
    try:
        for i, (name, frag, budget, extra, mode) in enumerate(SHOTS):
            stub_name = "stub%d.js" % i          # 每张一个文件名，避开 Chrome 的缓存
            open(os.path.join(tmp, stub_name), "w", encoding="utf-8", newline="\n").write(
                STUB.replace("MODE", mode))
            html = base.replace("</head>",
                                '<script src="/%s"></script></head>' % stub_name, 1)
            open(idx, "w", encoding="utf-8", newline="").write(
                html.replace("</body>", "<script>%s</script></body>" % extra, 1))
            png = os.path.join(OUT, "v13-%s.png" % name)
            cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                   "--user-data-dir=" + profile, "--screenshot=" + png,
                   "--window-size=1200,900", "--virtual-time-budget=%d" % budget,
                   "--force-device-scale-factor=1", url + frag]
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            print(name, "exit", r.returncode, os.path.getsize(png) if os.path.exists(png) else 0)
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)
    return 0


sys.exit(main())
