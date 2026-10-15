"""
tmp/ 临时环境（用完即弃）：把 dist 喂给手机尺寸的浏览器，同时用**真后端**回答 /_api。

为什么要有它：安卓壳里还没有桥（P0 未做），装到设备上页面只能显示"pywebview api 还没就绪"，
详情页 / 搜索页根本走不到。这里在 PC 上起一个服务，页面里塞一份假桥（tmp/_pc_bridge.js），
假桥把调用转成 POST /_api 交给真正的 API 对象 —— 于是手机尺寸下看到的是**真数据**的版式。

跑法： .venv\Scripts\python.exe tmp\_pc_bridge_server.py
手机： adb reverse tcp:47755 tcp:47755 之后用浏览器开 http://127.0.0.1:47755/
"""
import json
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PORT = 47755

# 别碰真实用户目录（~/.jmreader）：缓存 / 数据库 / 配置全落到 tmp/_pcapp 下
os.environ.setdefault("GUZHU_APP_DIR", str(ROOT / "tmp" / "_pcapp"))
sys.path.insert(0, str(ROOT))

import backend.paths as paths                      # noqa: E402
from backend.api import API                        # noqa: E402
from backend.config import load_config             # noqa: E402

DIST = ROOT / "frontend" / "dist"
SHIM = ROOT / "tmp" / "_pc_bridge.js"
BASE = f"http://127.0.0.1:{PORT}"

api = API(base_url=BASE)
# 预热一次：图源第一次握手要建客户端，慢的话页面会先闪一下错误态
threading.Thread(target=lambda: api.get_ranking("day", "all", 1, "views"), daemon=True).start()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def translate_path(self, path):
        clean = urlparse(path).path
        for prefix, root in (("/images", paths.IMG_DIR),):
            if clean.startswith(prefix + "/"):
                parts = [p for p in clean[len(prefix) + 1:].split("/") if p not in ("", ".", "..")]
                return str(root.joinpath(*parts))
        return super().translate_path(path)

    def do_GET(self):
        clean = urlparse(self.path).path
        if clean in ("/", "/index.html") or clean == "/_pc_bridge.js":
            if clean == "/_pc_bridge.js":
                body = SHIM.read_bytes()
                ctype = "text/javascript; charset=utf-8"
            else:
                html = (DIST / "index.html").read_text(encoding="utf-8")
                tag = '<script src="/_pc_bridge.js"></script>'
                # 假桥必须排在模块脚本前面：页面一跑就要看到 window.pywebview
                html = html.replace('<script type="module"', tag + '\n    <script type="module"', 1)
                body = html.encode("utf-8")
                ctype = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path == "/report":
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            print("[report] " + raw.decode("utf-8", "replace"), flush=True)
            self.send_response(204)
            self.end_headers()
            return
        if urlparse(self.path).path != "/_api":
            self.send_error(404)
            return
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        print("[post] " + raw.decode("utf-8", "replace")[:160], flush=True)
        try:
            payload = json.loads(raw.decode("utf-8"))
            name = str(payload["name"])
            args = list(payload.get("args") or [])
            if name.startswith("_") or not hasattr(api, name):
                raise AttributeError(f"没有这个方法：{name}")
            print(f"[api] {name} {args}", flush=True)
            result = getattr(api, name)(*args)
            out = {"__result__": result}
        except Exception as exc:                     # 原样回给页面，跟 pywebview 的拒绝对齐
            out = {"__error__": f"{type(exc).__name__}: {exc}"}
        body = json.dumps(out, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[req] " + (fmt % args), flush=True)


if __name__ == "__main__":
    print(f"PC 假桥服务：{BASE}   dist={DIST}", flush=True)
    print(f"用户目录（本次）：{paths.APP_DIR}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()