# -*- coding: utf-8 -*-
"""品牌行（字标只取代「孤竹」，「漫画」留着）的验收：4 张无头截图 + 一份 DOM 断言。
   dist 拷临时目录、插假 pywebview 桥（普通对象，不用 Proxy）、起本地静态服务。
   断言（--dump-dom，虚拟时间 6s 之后）：`.brand-slot` 里真的落了字标、品牌行只剩「漫画」、
   落位后全文档只剩一份 `aria-label="GuZhu"`（闪屏那层已经撤掉，没跟导航重复）。"""
import functools, http.server, os, re, shutil, socket, subprocess, sys, tempfile, threading

REPO = r"D:\guzhu_comic"
OUT = os.path.join(REPO, "tmp", "_ui")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
window.pywebview = { api: {
  get_settings: function () { return Promise.resolve({}); },
  prefetch_home: function () { return Promise.resolve(null); },
  get_ranking: function () { return Promise.resolve([]); },
  get_history: function () { return Promise.resolve([]); },
  get_recommendations: function () { return Promise.resolve({ items: [], cold: true }); }
} };
"""

# name, hash, w, h, 虚拟时间预算（ms）, 额外 JS
SHOTS = [
    ("brand-landed", "#/popular", 1200, 900, 5000, ""),
    ("brand-flight", "#/popular", 1200, 900, 2250, ""),
    ("brand-narrow", "#/popular", 1040, 800, 5000, ""),
    ("brand-light", "#/popular", 1200, 900, 5000,
     "document.documentElement.dataset.theme='light';"),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    tmp = os.path.join(tempfile.gettempdir(), "gz_brand")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
    idx = os.path.join(tmp, "index.html")
    html = open(idx, encoding="utf-8").read().replace(
        "</head>", '<script src="/stub.js"></script></head>', 1)
    assert "stub.js" in html
    open(idx, "w", encoding="utf-8", newline="").write(html)

    port = free_port()
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_brand_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    url = "http://127.0.0.1:%d/" % port
    ok = True
    try:
        for name, frag, w, h, budget, extra in SHOTS:
            body = ("<script>setTimeout(function(){%s},2000);</script>" % extra) if extra else ""
            open(idx, "w", encoding="utf-8", newline="").write(
                html.replace("</body>", body + "</body>", 1))
            png = os.path.join(OUT, "v10-%s.png" % name)
            cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                   "--user-data-dir=" + profile, "--screenshot=" + png,
                   "--window-size=%d,%d" % (w, h), "--virtual-time-budget=%d" % budget,
                   "--force-device-scale-factor=1", url + frag]
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            print("截图 %-14s rc=%d %s" % (name, r.returncode,
                  os.path.getsize(png) if os.path.exists(png) else "缺失"))
            try:
                from PIL import Image
                im = Image.open(png).crop((0, 0, 260, 110))
                im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(
                    os.path.join(OUT, "v10-%s-zoom.png" % name))
            except Exception as exc:
                print("  裁图跳过:", exc)

        # DOM 断言：等落位完（6s 虚拟时间）再看
        open(idx, "w", encoding="utf-8", newline="").write(html)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu",
                            "--user-data-dir=" + profile, "--dump-dom",
                            "--virtual-time-budget=6000", url + "#/popular"],
                           capture_output=True, timeout=180)
        dom = r.stdout.decode("utf-8", "replace")
        # 只取品牌行那一段（.brand-mark → .brand-sub）：main.ts 里那句注释也含「孤竹」，不能整篇搜
        row = dom.split('class="brand-sub"')[0].split('class="brand-mark"')[-1]
        checks = [
            ("字标落在 .brand-slot 里",
             re.search(r'class="brand-slot"[^>]*>\s*<svg', dom) is not None),
            ("品牌行留着「漫画」", "漫画" in row),
            ("兜底文案「孤竹」已被换掉", "孤竹" not in row),
            ("闪屏那层已撤（全文档只剩一份 GuZhu 字标）",
             dom.count('aria-label="GuZhu"') == 1),
        ]
        for label, passed in checks:
            print("%-4s %s" % ("PASS" if passed else "FAIL", label))
            ok = ok and passed
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)

    print("ALL PASS" if ok else "有 FAIL")
    return 0 if ok else 1


sys.exit(main())