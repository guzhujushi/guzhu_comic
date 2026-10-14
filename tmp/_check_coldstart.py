# -*- coding: utf-8 -*-
r"""冷启动复现（回归检查）：模拟 pywebview 的「两步注入」—— ① 先建空对象 {api:{}}，
② 2 秒后才把方法挂上并派发 pywebviewready。检查到达首页后「推荐段」和左下角「继续阅读」
有没有铺出来。

为什么要有这个检查：pywebview 的 js/api.js 先建空对象、js/finish.js 才挂方法，期间
`window.pywebview.api` **判真**。旧代码（HEAD）只判「对象在」就开路由，于是首页那两块
一次性代码一看没有自己要的方法就把自己永久藏起来。实测旧包 recHidden=true /
resumeHidden=true，现包 recCards=5 / 卡片有标题 —— 这个脚本能抓住它。

用法：
    .venv\Scripts\python.exe tmp\_check_coldstart.py                 # 只测 frontend/dist
    .venv\Scripts\python.exe tmp\_check_coldstart.py tmp\_dist_old  # 连修复前那版一起测（应 FAIL）
（tmp\_dist_old = 修复前那版 dist 的存档，留着做对照；想重造：git checkout HEAD -- webstatus.ts
main.ts components/recommend.ts resume.ts → npm --prefix frontend run build → 把 dist 拷成
tmp\_dist_old → 再把改动的 4 个文件拷回去。）"""
import functools, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

HISTORY = ("[{album_id:'422866',photo_id:'530000',page_index:41,title:'测试本子',"
           "cover_url:'/apple-touch-icon.png',updated_at:1750000000}]")

REC = ("{ cold: true, items: [1,2,3,4,5].map(function (i) { return {"
       " id: String(1000+i), title: '推荐漫画 ' + i, cover_url: '/apple-touch-icon.png',"
       " subtitle: '作者：测试', favorited: false }; }) }")

STUB = """
window.pywebview = { api: {} };                      // ① 空对象（js/api.js 就是这么干的）
var REC = REC_JS;
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(null); },
  get_ranking: function () { return Promise.resolve([]); },
  get_albums: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve(HISTORY_JS); },
  get_recommendations: function () { return Promise.resolve(REC); }
};
window.setTimeout(function () {                      // ② 两秒后才把方法挂上
  for (var k in stub) window.pywebview.api[k] = stub[k];
  window.dispatchEvent(new Event('pywebviewready'));
}, 2000);
"""

MARK = """<script>setTimeout(function () {
  var rec = document.querySelector('.rec-section');
  var row = rec && rec.querySelector('.rec-row');
  var res = document.querySelector('.nav-resume');
  var card = res && res.querySelector('.resume-card');
  var out = {
    apiMethods: Object.keys(window.pywebview.api).length,
    recHidden: rec ? rec.hidden : null,
    recCards: row ? row.children.length : -1,
    recName: rec ? rec.querySelector('.rec-name').textContent : null,
    resumeHidden: res ? res.hidden : null,
    resumeTitle: card ? card.querySelector('.resume-title').textContent : null,
    resumeHref: card ? card.getAttribute('href') : null
  };
  document.title = 'R|' + JSON.stringify(out);
}, 6000);</script>"""


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def run(tag, src):
    tmp = os.path.join(tempfile.gettempdir(), "gz_cold_" + tag)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp)
    idx = os.path.join(tmp, "index.html")
    html = open(idx, encoding="utf-8").read()
    html = html.replace("</head>", '<script src="/stub.js"></script></head>', 1)
    html = html.replace("</body>", MARK + "</body>", 1)
    open(idx, "w", encoding="utf-8", newline="").write(html)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(
        STUB.replace("REC_JS", REC).replace("HISTORY_JS", HISTORY))

    port = free_port()
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a, **k: None   # 别把请求日志刷满屏
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    profile = os.path.join(tempfile.gettempdir(), "gz_cold_profile_" + tag)
    shutil.rmtree(profile, ignore_errors=True)
    try:
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--user-data-dir=" + profile,
                            "--window-size=1200,900", "--virtual-time-budget=12000", "--dump-dom",
                            "http://127.0.0.1:%d/#/popular" % port],
                           capture_output=True, timeout=240, text=True, encoding="utf-8",
                           errors="replace")
        m = re.search(r"<title>R\|(\{.*?\})</title>", r.stdout or "", re.S)
        return json.loads(m.group(1)) if m else None
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


dirs = sys.argv[1:] or [os.path.join(REPO, "frontend", "dist")]
bad = 0
for src in dirs:
    tag = os.path.basename(src.rstrip("\\/")) or src
    got = run(tag, src)
    if got is None:
        print(tag, "FAIL 拿不到结果（页面没跑起来？）"); bad += 1; continue
    ok = (got["recHidden"] is False and got["recCards"] > 0
          and got["resumeHidden"] is False and bool(got["resumeTitle"]))
    bad += 0 if ok else 1
    print("%s %-18s %s" % ("PASS" if ok else "FAIL", tag, json.dumps(got, ensure_ascii=True)))
print("=> %s" % ("全部通过" if bad == 0 else "有 %d 个不达标" % bad))
sys.exit(1 if bad else 0)
