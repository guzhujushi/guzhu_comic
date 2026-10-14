# -*- coding: utf-8 -*-
"""重注入回归检查：用**真的** pywebview 桥代码（js/api.js + js/finish.js）+ 一个假 Python 端，
复现"启动时注了两遍、第二遍把正在飞的调用的回调表清掉"这个真机故障。

为什么必须这么做：假桥（普通对象）没有 `_returnValuesCallbacks` 这套机制，根本复现不出
"promise 永远不 settle"。这里把 api.js 原样搬过来，`_jsApiCallback` 换成"延迟 LATENCY 之后
按 pywebview 的方式回调 `_returnValuesCallbacks[func][id]({value})`"，再在调用飞行中敲一次
`_createApi()`（= 第二次注入的 finish.js，它会把回调表整个重建）—— 旧包就卡在这里（整个窗口
空白），现包应该照样把首页铺出来。

用法：
    .venv\\Scripts\\python.exe tmp\\_check_bridge_wipe.py                    # 只测 frontend/dist
    .venv\\Scripts\\python.exe tmp\\_check_bridge_wipe.py tmp\\_dist_old     # 连修复前那版一起测
"""
import functools, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PYWV_JS = os.path.join(REPO, ".venv", "Lib", "site-packages", "webview", "js")

# 页面启动路径上会用到的方法（名字/参数照 pywebview.d.ts 写，参数名必须是合法标识符）
FUNCS = [
    ("get_settings", []),
    ("get_history", ["limit"]),
    ("get_recommendations", ["kind", "limit", "exclude"]),
    ("get_ranking", ["time_range", "category", "page", "order_by"]),
    ("prefetch_home", ["time_range", "order_by"]),
    ("prefetch_albums", ["album_ids"]),
]
RESP = """
var RESP = {
  get_settings: {},
  get_history: [{ album_id: '422866', photo_id: '530000', page_index: 41,
                  title: '测试本子', cover_url: '/apple-touch-icon.png', updated_at: 1750000000 }],
  get_recommendations: { cold: true, items: [1,2,3,4,5].map(function (i) { return {
      id: String(1000 + i), title: '推荐漫画 ' + i, cover_url: '/apple-touch-icon.png',
      subtitle: '作者：测试', favorited: false }; }) },
  get_ranking: [],
  prefetch_home: 0,
  prefetch_albums: 0
};
"""

BRIDGE = """
/* 桥驱动：照 pywebview 的两步注入来 —— 先 api.js 建空对象（由上一段 <script> 完成），
   finish.js 才 _createApi() 挂方法并派发 pywebviewready。 */
(function () {
  window.pywebview.platform = 'edgechromium';
  window.pywebview.stringify = function (o) { return JSON.stringify(o); };
  var LATENCY = LATENCY_MS;
  /* 假 Python 端：就是 util.py 里 js_bridge_call 干的事（延迟之后回头调回调表） */
  window.pywebview._jsApiCallback = function (funcName, params, id) {
    setTimeout(function () {
      window.pywebview._returnValuesCallbacks[funcName][id](
        { value: JSON.stringify(RESP[funcName] === undefined ? null : RESP[funcName]) });
    }, LATENCY);
  };
  function inject() {
    window.pywebview._createApi(FUNC_LIST);         /* ← 这一句会把在飞的回调表重建 */
    window.dispatchEvent(new CustomEvent('pywebviewready'));
  }
  INJECT_AT.forEach(function (ms) { setTimeout(inject, ms); });
  window.__gzErrors = [];
  window.addEventListener('unhandledrejection', function (e) {
    window.__gzErrors.push(String((e.reason && e.reason.message) || e.reason));
  });
})();
"""

MARK = """<script>setTimeout(function () {
  var rec = document.querySelector('.rec-section');
  var row = rec && rec.querySelector('.rec-row');
  var res = document.querySelector('.nav-resume');
  var out = {
    appKids: document.querySelectorAll('#app > *').length,
    recHidden: rec ? rec.hidden : null,
    recCards: row ? row.children.length : -1,
    resumeHidden: res ? res.hidden : null,
    resumeTitle: res ? (res.querySelector('.resume-title') || {}).textContent : null,
    errors: (window.__gzErrors || []).length
  };
  document.title = 'R|' + JSON.stringify(out);
}, 9000);</script>"""

SCENARIOS = [
    # 名字, 两次注入的时间（ms）, 假 Python 的回包延迟（ms）
    ("double-early", [300, 340], 1200),    # 两遍紧挨着：启动闸门必须等它安静下来
    ("late-second", [300, 1600], 2600),    # 第二遍在人已经开工之后才落：靠 bridgeCall 重试救回来
]


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def build_pywebview_js(tmp, func_list):
    """把 pywebview 真的 api.js / finish.js 搬过去（占位符照它 load_js_files 的方式替换）"""
    api = open(os.path.join(PYWV_JS, "api.js"), encoding="utf-8").read()
    api = api.replace("'%(token)s'", "'testtoken'").replace("'%(platform)s'", "'edgechromium'")
    open(os.path.join(tmp, "pywv_api.js"), "w", encoding="utf-8", newline="\n").write(api)
    fin = open(os.path.join(PYWV_JS, "finish.js"), encoding="utf-8").read()
    fin = fin.replace("%(functions)s", json.dumps(json.dumps(func_list))[1:-1])
    open(os.path.join(tmp, "pywv_finish.js"), "w", encoding="utf-8", newline="\n").write(fin)


def run(tag, src, scenario, inject_at, latency):
    tmp = os.path.join(tempfile.gettempdir(), "gz_wipe_" + tag)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp)
    func_list = [{"func": n, "params": p} for n, p in FUNCS]
    build_pywebview_js(tmp, func_list)

    idx = os.path.join(tmp, "index.html")
    html = open(idx, encoding="utf-8").read()
    # 顺序：api.js（建空对象）→ 桥驱动 → finish.js（挂方法 + 派发 ready），跟真机一致
    head = ('<script src="/pywv_api.js"></script>\n'
            '    <script>' + RESP + '</script>\n'
            '    <script>' + BRIDGE.replace("LATENCY_MS", str(latency))
            .replace("FUNC_LIST", json.dumps(func_list))
            .replace("INJECT_AT", json.dumps(inject_at)) + '</script>\n'
            '    <script src="/pywv_finish.js"></script>\n')
    html = html.replace("</head>", head + "  </head>", 1)
    html = html.replace("</body>", MARK + "</body>", 1)
    open(idx, "w", encoding="utf-8", newline="").write(html)

    port = free_port()
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    profile = os.path.join(tempfile.gettempdir(), "gz_wipe_profile_" + tag + scenario)
    shutil.rmtree(profile, ignore_errors=True)
    try:
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--user-data-dir=" + profile,
                            "--window-size=1200,900", "--virtual-time-budget=11000", "--dump-dom",
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
    for name, inject_at, latency in SCENARIOS:
        got = run(tag, src, name, inject_at, latency)
        if got is None:
            print("FAIL %-10s %-13s 拿不到结果（页面没跑起来？）" % (tag, name)); bad += 1; continue
        ok = (got["appKids"] > 0 and got["recHidden"] is False and got["recCards"] > 0
              and got["resumeHidden"] is False and bool(got["resumeTitle"]))
        bad += 0 if ok else 1
        print("%s %-10s %-13s %s" % ("PASS" if ok else "FAIL", tag, name,
                                     json.dumps(got, ensure_ascii=True)))
print("=> %s" % ("全部通过" if bad == 0 else "有 %d 个不达标" % bad))
sys.exit(1 if bad else 0)
