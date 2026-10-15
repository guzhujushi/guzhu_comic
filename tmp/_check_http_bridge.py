# -*- coding: utf-8 -*-
"""
P0 验收：桥从 pywebview 的 `js_api` 换成**本地 HTTP JSON-RPC + token** 之后，两层都要对。

  ① HTTP 层（不依赖图源）：`/api`、`/images`、`/downloads` 不带 token 一律打不动；带对 token 才通；
     私有名（`_jm`）与不存在的方法一律拒绝；Host 不是回环一律 403。
  ② 页面层（无头 Chrome + **真后端**）：前端垫片 `frontend/src/bridge.ts` 真能把
     `window.pywebview.api.X(...)` 接到 `POST /api` 上，而且首页照铺真数据。

页面层怎么验：把 dist **拷一份**（不动真产物），在 `</body>` 前注入一段标记脚本 —— 它过 1.2 秒
自己调三个桥方法（两个不碰图源：`get_version` / `get_settings`；一个必须被拒：`_jm`），
把结果与页面统计写进 `document.title`，脚本再用 `--dump-dom` 抓回来判。

用户目录落在 `tmp/_p0app`，不碰 `~/.jmreader`。
"""
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("GUZHU_APP_DIR", str(ROOT / "tmp" / "_p0app"))
sys.path.insert(0, str(ROOT))

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DIST = ROOT / "frontend" / "dist"
USERS = str(ROOT / "tmp" / "_p0app")

from backend import bridge, paths                    # noqa: E402
from backend.api import API                          # noqa: E402
from backend.server import start_static_server       # noqa: E402

fails: list[str] = []
oks: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (oks if ok else fails).append(name + (f"  [{detail}]" if detail else ""))
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"  {detail}" if detail else ""), flush=True)


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def get(port: int, path: str, host: str | None = None) -> int:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    conn.request("GET", path, headers={"Host": host} if host else {})
    resp = conn.getresponse(); resp.read(); conn.close()
    return resp.status


def post(port: int, path: str, payload: dict | None, token: str | None = None) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["X-Guzhu-Token"] = token
    conn.request("POST", path, body=json.dumps(payload or {}).encode("utf-8"), headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", "replace")
    conn.close()
    try:
        return resp.status, json.loads(raw)
    except ValueError:
        return resp.status, {"__raw__": raw[:200]}


# ---------------------------------------------------------------- 注入标记的那份 dist
MARK = """<script>document.title = 'P0PENDING';
setTimeout(async function () {
  var out = {};
  try {
    var v = await window.pywebview.api.get_version();
    out.version = (v && v.app) || 'null';
  } catch (e) { out.errVersion = String(e); }
  try {
    var s = await window.pywebview.api.get_settings();
    out.settings = !!(s && s.window);
  } catch (e) { out.errSettings = String(e); }
  try { await window.pywebview.api._jm(); out.private = 'FAIL 私有方法也能调'; }
  catch (e) { out.private = String(e).slice(0, 60); }
  out.cards = document.querySelectorAll('album-card').length;   // 作品卡是自定义元素 <album-card>
  out.noBridge = document.body.innerText.indexOf('桥没连上') >= 0;
  out.snippet = document.body.innerText.replace(/\\s+/g, ' ').slice(0, 90);
  document.title = 'P0|' + JSON.stringify(out);
}, 1200);</script>"""

profile = os.path.join(tempfile.gettempdir(), "gz_p0_chrome")
work = os.path.join(tempfile.gettempdir(), "gz_p0_dist")
shutil.rmtree(profile, ignore_errors=True)
shutil.rmtree(work, ignore_errors=True)
shutil.copytree(DIST, work)
idx = Path(work) / "index.html"
html = idx.read_text(encoding="utf-8")
assert "</body>" in html, "index.html 里没有 </body>，标记注不进去"
idx.write_text(html.replace("</body>", MARK + "</body>", 1), encoding="utf-8", newline="")

# ---------------------------------------------------------------- 起服务
PORT = free_port()
TOKEN = bridge.new_token()
api = API(base_url="", token=TOKEN)
base = start_static_server(
    Path(work),
    {"/images": paths.IMG_DIR, "/downloads": paths.resolve_download_dir("~/.jmreader/downloads")},
    PORT, token=TOKEN, rpc=bridge.make_rpc(api),
)
api.img_base = base
print(f"服务：{base}（token 前 8 位 {TOKEN[:8]}…，用户目录 {USERS}）\n", flush=True)

print("① HTTP 层", flush=True)
check("GET / 不带 token → 200（静态资源不设防）", get(PORT, "/") == 200)
check("GET /apple-touch-icon.png 不带 token → 200", get(PORT, "/apple-touch-icon.png") == 200)
check("GET /images/... 不带 token → 403", get(PORT, "/images/422866/00001.webp") == 403)
check("GET /downloads/... 不带 token → 403", get(PORT, "/downloads/1/2/3.webp") == 403)
img_t = get(PORT, f"/images/422866/00001.webp?t={TOKEN}")
check("GET /images/... 带 ?t= → 放行（404 是因为这张图不在本地，不是 403）", img_t != 403, f"HTTP {img_t}")
check("GET /images/... 带错 token → 403", get(PORT, "/images/422866/00001.webp?t=nope") == 403)
check("Host 不是回环 → 403", get(PORT, "/", host="evil.example.com") == 403)

st, data = post(PORT, "/api", {"name": "get_version", "args": []})
check("POST /api 不带 token → 403", st == 403 and "token" in str(data.get("__error__", "")), str(data)[:110])
st, _ = post(PORT, "/api", {"name": "get_version", "args": []}, token="nope")
check("POST /api 带错 token → 403", st == 403)
st, data = post(PORT, "/api", {"name": "get_version", "args": []}, token=TOKEN)
ver = data.get("__result__") or {}
check("POST /api 带对 token → 200 且有 __result__", st == 200 and "app" in ver,
      f"HTTP {st} app={ver.get('app')} frozen={ver.get('frozen')}")
st, data = post(PORT, "/api", {"name": "get_settings", "args": []}, token=TOKEN)
check("get_settings 真读到了配置（有 window 组）", st == 200 and "window" in (data.get("__result__") or {}))
for bad, why in (("_jm", "私有名"), ("img_base", "非方法属性"), ("no_such_method", "不存在的方法")):
    st, data = post(PORT, "/api", {"name": bad, "args": []}, token=TOKEN)
    check(f"{why} {bad} 被拒", st == 200 and "没有这个方法" in str(data.get("__error__", "")),
          str(data.get("__error__"))[:60])
st, data = post(PORT, "/api", {"name": "get_ranking", "args": ["day", "all", 1, "views"]}, token=TOKEN)
rank = data.get("__result__")
check("真调用 get_ranking 拿到榜单（图源通）", st == 200 and isinstance(rank, list) and len(rank) > 0,
      f"{len(rank) if isinstance(rank, list) else 'err'} 条 {(data.get('__error__') or '')[:70]}")


def chrome_dom(url: str, budget: int) -> str:
    r = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
         "--window-size=1200,900", f"--virtual-time-budget={budget}", "--dump-dom", url],
        capture_output=True, timeout=300, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


print("\n② 页面层（无头 Chrome，垫片 → 真 /api）", flush=True)
dom = chrome_dom(f"{base}/?t={TOKEN}", 25000)
m = re.search(r"<title>(.*?)</title>", dom, re.S)
title = (m.group(1) if m else "").strip()
got: dict = {}
if "P0|" in title:
    try:
        got = json.loads(title.split("P0|", 1)[1])
    except ValueError:
        got = {}
check("标记脚本跑到了（页面 title 回来了）", bool(got), f"title={title[:60]!r}")
check("页面里 window.pywebview.api.get_version() 走通了 HTTP 桥",
      got.get("version", "null") not in ("", "null") and not got.get("errVersion"),
      f"version={got.get('version')} errVersion={got.get('errVersion')}")
check("get_settings 也通", got.get("settings") is True, f"errSettings={got.get('errSettings')}")
check("私有方法 _jm 在前端也被拒", "没有这个方法" in str(got.get("private", "")), str(got.get("private"))[:70])
check("首页铺出了作品卡（真数据，不是版式空壳）", (got.get("cards") or 0) > 0,
      f"cards={got.get('cards')} 正文={(got.get('snippet') or '')[:60]!r}")
check("页面**没有**出现「桥没连上」", got.get("noBridge") is False)

dom2 = chrome_dom(f"{base}/", 25000)          # 不带 token：静态页面照开，但页面要明说
check("不带 token 打开页面 → 提示「桥没连上：…?t=…」", "桥没连上" in dom2)

shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(profile, ignore_errors=True)

print("\n================================", flush=True)
print(f"PASS {len(oks)}  FAIL {len(fails)}", flush=True)
for f in fails:
    print("  FAIL:", f, flush=True)
sys.exit(1 if fails else 0)