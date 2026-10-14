# -*- coding: utf-8 -*-
"""阅读器浮层：出两张图（目录开 / 设置开），顺便核对面板确实开着。"""
import functools, http.server, os, re, shutil, socket, subprocess, tempfile, threading
REPO = r"D:\guzhu_comic"
OUT = os.path.join(REPO, "tmp", "_ui")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STUB = open(os.path.join(REPO, "tmp", "_check_reader_sheet.py"), encoding="utf-8").read()
STUB = STUB[STUB.index('STUB = """') + 10:STUB.index('"""', STUB.index('STUB = """') + 10)]
SHOT = "<script>setTimeout(function(){document.querySelector('%s').click();}, 2800);</script>"

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

tmp = os.path.join(tempfile.gettempdir(), "gz_reader_shot")
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
idx = os.path.join(tmp, "index.html")
html = open(idx, encoding="utf-8").read().replace("</head>", '<script src="/stub.js"></script></head>', 1)
port = free_port()
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
profile = os.path.join(tempfile.gettempdir(), "gz_reader_shot_chrome")
shutil.rmtree(profile, ignore_errors=True)
url = "http://127.0.0.1:%d/#/read?photo_id=530000&album_id=209827" % port
try:
    for name, sel in (("chapters", ".chapters-btn"), ("settings", ".settings-btn")):
        open(idx, "w", encoding="utf-8", newline="").write(html.replace("</body>", SHOT % sel + "</body>", 1))
        png = os.path.join(OUT, "v9-reader-%s.png" % name)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--user-data-dir=" + profile, "--screenshot=" + png,
                            "--window-size=1200,900", "--virtual-time-budget=9000",
                            "--force-device-scale-factor=1", url],
                           capture_output=True, timeout=180)
        print(name, "rc=%d" % r.returncode, os.path.getsize(png) if os.path.exists(png) else "缺失")
finally:
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(profile, ignore_errors=True)