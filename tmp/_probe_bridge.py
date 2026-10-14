# -*- coding: utf-8 -*-
"""真窗口探针（用完即删）：起一次真 pywebview，12 秒后回报首页铺得怎么样。

回答的就是「第一次进首页到底渲染出来没有」：`appKids` 是不是 0（0 = 整窗空白）、推荐段有没有出来、
卡片几张、左下角「继续阅读」有没有铺出来。

三路仪器，专门盯 pywebview「启动注两遍把回调清掉」这个坑：

  1. `inject_pywebview` 被调了几次、各在什么时候 —— 这就是「注了两遍」的源头
     （WebView2 会给每次 NavigationCompleted 各注入一遍，真页面 / 重载都算一次）；
  2. 后端 `get_settings` / `get_history` / `prefetch_home` 被 JS 调到的时刻（= 桥真的挂上方法了）；
  3. `evaluate_js` 送返回值那一步（`window.pywebview._returnValuesCallbacks[func][id](...)`）
     有没有炸 —— 炸了就是真机报的那个 `is not a function`，页面会整片空白。

跑法：
    .venv\\Scripts\\python.exe tmp\\_probe_bridge.py            # 走 config.yaml 的 dev.url（vite 5173）
    .venv\\Scripts\\python.exe tmp\\_probe_bridge.py --dist     # 另起一个静态服务喂 frontend/dist（打包后的样子）
"""
import json
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, r"D:\guzhu_comic")

import webview
from backend.api import API
from backend.config import load_config

cfg = load_config()
api = API()
T0 = time.time()
OUT = {}
EVENTS = []
LOCK = threading.Lock()

# 12 秒够首页铺完（正常 <2s），也够那两遍注入都发生
WAIT_S = 12


def note(kind, detail=""):
    with LOCK:
        EVENTS.append([int((time.time() - T0) * 1000), kind, str(detail)[:160]])


def probe_url():
    """--dist：把 frontend/dist 当静态站喂出去，模拟打包后（不走 vite）；否则走 dev.url"""
    if "--dist" not in sys.argv:
        return cfg["dev"]["url"], None
    dist = Path(r"D:\guzhu_comic\frontend\dist")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(dist)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    note("dist-server", f"port={server.server_address[1]}")
    return f"http://127.0.0.1:{server.server_address[1]}/index.html", server


# 1) 注入次数与时刻。edgechromium 是 `from webview.util import inject_pywebview` 拿的名字，
#    所以要打在它自己的模块命名空间上。
try:
    import webview.platforms.edgechromium as _ec

    _orig_inject = _ec.inject_pywebview

    def _inject(platform, window):
        note("inject", platform)
        return _orig_inject(platform, window)

    _ec.inject_pywebview = _inject
except Exception as e:            # 不在 Windows / 平台模块没装：仪器缺席，不影响主流程
    note("inject-hook-failed", repr(e)[:120])


# 2) 后端被 JS 调到的那一刻。包装函数带 `*a, **kw` 没关系：js/api.js 用 `arguments` 传参，
#    声明的形参只影响名字（探针只读时间，不改行为）。
WATCH = ("get_settings", "get_history", "prefetch_home", "get_ranking", "get_recommendations")
for _name in WATCH:
    _fn = getattr(api, _name, None)
    if not callable(_fn):
        note("missing-api", _name)
        continue

    def _wrap(fn=_fn, name=_name):
        def inner(*a, **kw):
            note("api-call", name)
            return fn(*a, **kw)
        return inner

    setattr(api, _name, _wrap())


DOM_SCRIPT = "JSON.stringify({" \
    "appKids: document.querySelectorAll('#app > *').length," \
    "rec: (function(){var r=document.querySelector('.rec-section'); return r ? (r.hidden ? 'hidden' : 'shown') : 'none';})()," \
    "recCards: document.querySelectorAll('.rec-section album-card').length," \
    "resume: (function(){var r=document.querySelector('.nav-resume'); return r ? (r.hidden ? 'hidden' : 'shown') : 'none';})()" \
    "})"


def boot():
    win = webview.windows[0]

    # 3) 接住 pywebview 送返回值那一步
    original = win.evaluate_js

    def patched(script, *a, **kw):
        is_return = "_returnValuesCallbacks" in script
        try:
            out = original(script, *a, **kw)
        except Exception as e:
            if is_return:
                note("return-value-FAIL", repr(e)[:160])
            raise
        if is_return:
            func = script.split("_returnValuesCallbacks", 1)[-1].split('"')[1] if '"' in script else "?"
            note("return-value-ok", func)
        return out

    win.evaluate_js = patched
    note("boot-thread")

    time.sleep(WAIT_S)
    for key, script in (("h1", "document.querySelector('h1') ? document.querySelector('h1').textContent.trim().slice(0, 40) : null"),
                        ("dom", DOM_SCRIPT)):
        try:
            OUT[key] = patched(script)
        except Exception as e:
            OUT[key + "_err"] = repr(e)[:200]
    try:
        win.destroy()
    except Exception as e:
        OUT["destroy"] = repr(e)


url, server = probe_url()
webview.create_window(title="probe", url=url, js_api=api, width=1000, height=760)
webview.start(boot, debug=False)
if server is not None:
    server.shutdown()

ev = EVENTS
injects = [t for t, k, d in ev if k == "inject"]
try:
    dom = json.loads(OUT.get("dom") or "null")
except Exception:
    dom = None

print("SUMMARY " + json.dumps({
    "url": url,
    "injects": injects,
    "injectGap": (injects[1] - injects[0]) if len(injects) > 1 else None,
    "bridgeFirstCallAt": next((t for t, k, d in ev if k == "api-call"), None),
    "returnValueOk": sorted({d for t, k, d in ev if k == "return-value-ok"}),
    "returnValueFAIL": [(t, d[:40]) for t, k, d in ev if k == "return-value-FAIL"],
    "missingApi": [d for t, k, d in ev if k == "missing-api"],
    "dom": dom if dom is not None else OUT.get("dom"),
    "domErr": OUT.get("dom_err"),
}, ensure_ascii=False), flush=True)