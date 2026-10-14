# -*- coding: utf-8 -*-
"""核对「hero 展示过的漫画不在下面再出现一次」（2026-10-14 用户要求）。

无头 Chrome + 假桥，喂一份**故意重叠**的榜单：
  - 全部（hero）：H1 H2 H3 H4 H5 H6  → hero 取前三 = H1 H2 H3
  - 同人：H2 H1 H3 D4 … D12          → 前三部正好是 hero 那三部（不去重就会重复出现）
  - 单本 / 短篇 / 韩漫 / 美漫：各自独立，一个都不跟 hero 撞
  - 推荐：候选池里也埋了 H1 H2 H3（后端按 exclude 剔掉）

验三件事：
  1. hero 铺的是 H1 H2 H3；
  2. 下图各分类横条里**一个 H 都没有**，而且长度跟没被去重的那些行一样（不是被削短了）；
  3. 推荐段的请求带上了 hero 那三部的 ID（exclude），铺出来的卡里也没有 H。

跑法：.venv\\Scripts\\python.exe tmp\\_check_hero_dedupe.py            # 只测 frontend/dist
      .venv\\Scripts\\python.exe tmp\\_check_hero_dedupe.py tmp\\_dist_old
"""
import functools, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
HERO_IDS = {"H1", "H2", "H3"}

STUB = r"""
var RANK = {
  all:    ['H1','H2','H3','H4','H5','H6'],
  doujin: ['H2','H1','H3','D4','D5','D6','D7','D8','D9','D10','D11','D12'],
  single: ['S1','S2','S3','S4','S5','S6'],
  short:  ['T1','T2','T3','T4','T5','T6'],
  hanman: ['C1','C2','C3','C4','C5','C6'],
  meiman: ['M1','M2','M3','M4','M5','M6']
};
var POOL = ['R1','R2','H1','R3','H2','R4','R5','H3','R6','R7'];
function c(id) { return { id: id, title: id, cover_url: '/apple-touch-icon.png' }; }
var stub = {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(null); },
  get_history: function () { return Promise.resolve([]); },
  get_ranking: function (range, category, page, sort) {
    var list = page > 1 ? [] : (RANK[category] || []);
    return Promise.resolve(list.map(c));
  },
  get_recommendations: function (kind, limit, exclude) {
    window.__recExclude = (exclude || []).slice();          // 记下来：前端到底有没有把 hero 传过来
    var skip = {};
    (exclude || []).forEach(function (x) { skip[x] = 1; });
    return Promise.resolve({ cold: true, items: POOL.filter(function (id) { return !skip[id]; }).map(c) });
  }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;                       // 别让桥被当成 thenable（踩过）
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

MARK = """<script>setTimeout(function () {
  function titles(nodes) {
    return Array.prototype.map.call(nodes, function (n) {
      var p = n.querySelector('p');
      return p ? p.textContent.trim() : '?';
    });
  }
  // .hero-title 是个 <span>，文字就在它自己身上（卡片才是 <p>）
  var out = {
    hero: Array.prototype.map.call(document.querySelectorAll('.hero-title'), function (n) {
      return n.textContent.trim();
    }),
    rows: {},
    rec: titles(document.querySelectorAll('.rec-row album-card')),
    recExclude: window.__recExclude || null
  };
  Array.prototype.forEach.call(document.querySelectorAll('.cat-section:not(.rec-section)'), function (s) {
    var name = s.querySelector('.cat-name');
    out.rows[name ? name.textContent.trim() : '?'] = titles(s.querySelectorAll('album-card'));
  });
  document.title = 'R|' + JSON.stringify(out);
}, 6000);</script>"""


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def run(tag, src):
    tmp = os.path.join(tempfile.gettempdir(), "gz_hero_" + tag)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp)
    idx = os.path.join(tmp, "index.html")
    html = open(idx, encoding="utf-8").read()
    html = html.replace("</head>", '<script src="/stub.js"></script></head>', 1)
    html = html.replace("</body>", MARK + "</body>", 1)
    open(idx, "w", encoding="utf-8", newline="").write(html)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)

    port = free_port()
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    profile = os.path.join(tempfile.gettempdir(), "gz_hero_profile_" + tag)
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


def judge(got):
    """返回 (是否通过, 说明列表)"""
    if got is None:
        return False, ["拿不到结果（页面没跑起来？）"]
    notes = []
    hero = got.get("hero") or []
    rows = got.get("rows") or {}
    rec = got.get("rec") or []
    excl = set(got.get("recExclude") or [])

    if hero[:3] != ["H1", "H2", "H3"]:
        notes.append("hero 不是前三部：%s" % hero)
    if "同人" not in rows:
        notes.append("同人那一行没铺出来（rows=%s）" % list(rows))
    else:
        dup = [t for t in rows["同人"] if t in HERO_IDS]
        if dup:
            notes.append("同人横条里又出现了 hero 那几部：%s" % dup)
    for name, item in rows.items():
        dup = [t for t in item if t in HERO_IDS]
        if dup:
            notes.append("%s 横条里重复了 hero：%s" % (name, dup))
        if not item:
            notes.append("%s 横条是空的" % name)
    # 去重之后不能变短：同人给的是 12 部，剔掉 3 部还剩 9 部，够铺满
    if rows and "同人" in rows:
        longest = max(len(v) for v in rows.values())
        if len(rows["同人"]) != longest:
            notes.append("同人横条被削短了：%d 张，别的行 %d 张" % (len(rows["同人"]), longest))
    if not excl >= HERO_IDS:
        notes.append("推荐段的 exclude 里没有 hero 那三部：%s" % sorted(excl))
    if not rec:
        notes.append("推荐段没铺出卡")
    dup = [t for t in rec if t in HERO_IDS]
    if dup:
        notes.append("推荐段里又出现了 hero：%s" % dup)
    return not notes, notes


dirs = sys.argv[1:] or [os.path.join(REPO, "frontend", "dist")]
bad = 0
for src in dirs:
    tag = os.path.basename(src.rstrip("\\/")) or src
    got = run(tag, src)
    ok, notes = judge(got)
    bad += 0 if ok else 1
    print("%s %-16s %s" % ("PASS" if ok else "FAIL", tag,
                           json.dumps(got, ensure_ascii=True) if ok else "; ".join(notes)))
print("=> %s" % ("全部通过" if bad == 0 else "有 %d 个不达标" % bad))
sys.exit(1 if bad else 0)