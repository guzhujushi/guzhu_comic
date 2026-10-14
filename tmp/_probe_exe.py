# -*- coding: utf-8 -*-
r"""冻结态冒烟探针：真 dist + 真 API() + 真 pywebview 窗口。

和 `_probe_app.py` 的区别：不靠 `evaluate_js`（它在无控制台构建下会卡在 pywebview 的
semaphore.acquire 上），而是**让页面自己**在 `pywebviewready` 之后通过真桥回调
`probe_report(tag, payload)` 把 DOM 状态送回 Python —— 走的就是产品自己的那条路。

源码态：.venv\Scripts\python.exe tmp\_probe_exe.py
冻结态：tmp\_exe\dist<shell>\<name>\<name>.exe
环境变量：PROBE_OUT=<结果落盘路径>
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
EXE_DIR = Path(sys.executable).resolve().parent
_default_out = (EXE_DIR / "probe_out.json") if FROZEN else (Path(__file__).resolve().parent / "probe_out.json")
OUT = Path(os.environ.get("PROBE_OUT") or _default_out)
RESULT: dict = {"steps": []}
_lock = threading.Lock()

PREFERRED = 47753

if FROZEN:
    SRC_DIST = Path(getattr(sys, "_MEIPASS", EXE_DIR)) / "dist"
else:
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    SRC_DIST = ROOT / "frontend" / "dist"


def step(name: str) -> None:
    with _lock:
        RESULT["steps"].append("%s@%.1fs" % (name, time.time() - T0))
    flush()


def flush() -> None:
    with _lock:
        payload = "PROBE_RESULT=" + json.dumps(RESULT, ensure_ascii=False)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(payload, encoding="utf-8")
    except Exception:
        pass
    try:
        print(payload)
    except Exception:
        pass


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory: Path) -> int:
    handler = partial(Quiet, directory=str(directory))
    for port in range(PREFERRED, PREFERRED + 8):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError:
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv.server_address[1]
    raise RuntimeError("没有空闲端口")


INJECT = """
<script>
(function () {
  function stats() {
    function cls(el) { return (el.className || el.tagName) + (el.hidden ? '[hidden]' : ''); }
    var store = 'n/a';
    try { localStorage.setItem('probe_t', '1'); store = localStorage.getItem('probe_t') === '1'; }
    catch (e) { store = 'THROW:' + e.name; }
    var w = window.pywebview && window.pywebview.api;
    return {
      readyState: document.readyState,
      bridged: typeof (w && w.get_ranking),
      splashGone: !document.querySelector('#splash'),
      cards: document.querySelectorAll('album-card').length,
      panelKids: Array.prototype.map.call(document.querySelectorAll('.board-panel > *'), cls),
      navItems: document.querySelectorAll('#nav a, #nav button').length,
      cssRules: (function () { try { return document.styleSheets.length } catch (e) { return 'X' } })(),
      localStorageWritable: store,
      origin: location.origin
    };
  }
  var sent = false;
  function report(tag) {
    if (sent) return;
    sent = true;
    try {
      window.pywebview.api.probe_report(tag, JSON.stringify(stats()));
    } catch (e) {
      try { window.pywebview.api.probe_report(tag + ':THROW:' + e.message, '{}'); } catch (e2) {}
    }
  }
  window.addEventListener('pywebviewready', function () { setTimeout(function () { report('ready+8s') }, 8000) });
  setTimeout(function () { report('fallback+14s') }, 14000);
})()
</script>
</body>"""


def make_root() -> Path:
    """把 dist 拷到临时目录，往 index.html 里塞一段页面自报的脚本（不动仓库里的 dist）"""
    root = Path(tempfile.mkdtemp(prefix="probe_dist_"))
    shutil.copytree(SRC_DIST, root, dirs_exist_ok=True)
    idx = root / "index.html"
    html = idx.read_text(encoding="utf-8")
    idx.write_text(html.replace("</body>", INJECT), encoding="utf-8")
    return root


def main() -> None:
    try:
        import faulthandler
        faulthandler.enable(open(OUT.with_suffix(".fault"), "a", encoding="utf-8"))
    except Exception:
        pass
    import webview

    from backend.api import API

    RESULT["frozen"] = FROZEN
    RESULT["exe_dir"] = str(EXE_DIR)
    RESULT["meipass"] = getattr(sys, "_MEIPASS", None)
    RESULT["stdout_repr"] = repr(sys.stdout)
    RESULT["dist_src"] = str(SRC_DIST)
    RESULT["dist_src_ok"] = SRC_DIST.is_dir()
    RESULT["dist_files"] = sorted(p.name for p in SRC_DIST.rglob("*") if p.is_file())
    RESULT["dlls"] = sorted(p.name for p in EXE_DIR.rglob("*.dll"))
    flush()

    root = make_root()
    step("dist-copied")
    port = serve(root)
    RESULT["port"] = port
    api = API()
    RESULT["api_methods"] = len([m for m in dir(api) if not m.startswith("_")])

    def probe_report(tag, payload):
        try:
            RESULT.setdefault("reports", []).append({"tag": tag, "payload": json.loads(payload)})
        except Exception as e:
            RESULT.setdefault("reports", []).append({"tag": tag, "raw": payload, "err": repr(e)})
        step("page-reported")
        threading.Timer(1.5, lambda: [w.destroy() for w in webview.windows]).start()
        return "ok"

    api.probe_report = probe_report
    step("api-ready")

    webview.create_window(
        title="probe", url=f"http://127.0.0.1:{port}/", js_api=api,
        width=1200, height=800, background_color="#07080a",
    )
    step("window-created")
    # 冻结态必须持久化：默认 private_mode=True 会把 WebView2 的 user data 丢到临时目录，
    # localStorage（主题 / 榜单偏好）每次开窗都清空。
    webview.start(None, debug=False, private_mode=False,
                  storage_path=str(Path.home() / ".jmreader" / "webview"))
    step("start-returned")
    time.sleep(1.0)
    flush()


T0 = time.time()
try:
    main()
except Exception:
    RESULT["fatal"] = traceback.format_exc()
    flush()
    sys.exit(1)