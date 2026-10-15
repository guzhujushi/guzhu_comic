# -*- coding: utf-8 -*-
r"""安卓启动入口（`android_boot.start`）的回归 —— 不用设备，在桌面进程里按安卓的口径跑。

`android_boot.start()` 就是把 `GUZHU_APP_DIR` / `GUZHU_DIST_DIR` 递进来再起服务，所以桌面进程
里能整条跑通（`backend/paths.py` 认的就是这两个环境变量）。验五件事：

  ① 首次启动：返回带 `?t=` 的地址、页面是包内 dist、没有覆盖层时不留 `boot.json`；
  ② 这条路（安卓唯一的桥）token 闸门成立：`/api`、`/images` 不带 token 一律 403，带上才通；
  ③ **热更兜底**：上一份覆盖层"没起来"（`boot.json` 写着 ok=false）→ 这次开窗前先撤掉它、
     退回 `web.old`，页面直接是上一版，并留一笔"这次这份等报到"；
  ④ 前端真来报到（`notify_booted`）之后，看门狗不该把它记成坏的；
  ⑤ 没人报到 → 看门狗把 ok 记成 false（下次开窗就会撤掉）。

桌面上这五条分别由 `_check_updater.py`（39 项）与 `main.py` 覆盖；这一支盯的是**安卓壳这一声有没有接上**
（2026-10-15 之前漏着，热更下来的前端一旦白屏，用户只能清数据）。
"""
import http.client
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(r"D:\guzhu_comic")
ANDROID_PY = REPO / "android" / "app" / "src" / "main" / "python"

TMP = Path(tempfile.mkdtemp(prefix="gz_android_boot_"))
APP = TMP / "files"
DIST = TMP / "dist"

# 必须先立好目录与环境变量：`backend.paths` 是在 import 期就把 APP_DIR 算死的
(DIST / "assets").mkdir(parents=True)
(DIST / "index.html").write_text("<!doctype html><title>DIST-PAGE</title>DIST-PAGE", encoding="utf-8")
APP.mkdir(parents=True)
os.environ["GUZHU_APP_DIR"] = str(APP)
os.environ["GUZHU_DIST_DIR"] = str(DIST)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ANDROID_PY))

import android_boot                     # noqa: E402
from backend import updater             # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"    {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def get(url, token=None):
    from urllib.parse import urlparse
    u = urlparse(url)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=20)
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", "replace")
    conn.close()
    return resp.status, body


def post(base, payload, token=None):
    u = base.split("//", 1)[1]
    host, _, port = u.partition(":")
    conn = http.client.HTTPConnection(host, int(port.split("/")[0]), timeout=60)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Guzhu-Token"] = token
    conn.request("POST", "/api", body=json.dumps(payload).encode("utf-8"), headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", "replace")
    conn.close()
    try:
        return resp.status, json.loads(raw)
    except ValueError:
        return resp.status, {"__raw__": raw[:120]}


def state():
    f = APP / "boot.json"
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def bad_files():
    return sorted(p.name for p in APP.glob("web.broken*"))


# ---------------------------------------------------------------- ① 首次启动
print("\n① 首次启动（还没有热更覆盖层）", flush=True)
url1 = android_boot.start(str(APP), str(DIST))
check("返回的地址带 ?t=（安卓就靠它把桥递给页面）", "?t=" in url1, url1.split("?")[0])
base1, token1 = url1.split("/?", 1)
token1 = token1.split("=", 1)[1]
code, body = get(url1)
check("页面拿得到，而且是包内 dist 那份", code == 200 and "DIST-PAGE" in body, f"code={code}")
check("没有覆盖层时不留 boot.json（不瞎记）", not (APP / "boot.json").exists())

# ---------------------------------------------------------------- ② token 闸门
print("\n② 桥 / 图片的 token 闸门（安卓只有这一条路）", flush=True)
code, _ = post(base1, {"name": "get_version", "args": []})
check("/api 不带 token → 403", code == 403, f"code={code}")
code, payload = post(base1, {"name": "get_version", "args": []}, token1)
check("/api 带对 token → 通", code == 200 and "__result__" in payload,
      f"code={code} keys={list(payload)[:2]}")
code, _ = get(base1 + "/images/9001/1.jpg")
check("/images 不带 token → 403（同机别的程序读不到）", code == 403, f"code={code}")

# ---------------------------------------------------------------- ③ 热更兜底：上一份没起来
print("\n③ 上一份热更前端「没起来」→ 这次开窗前就撤掉它", flush=True)
(APP / "web").mkdir()
(APP / "web" / "index.html").write_text("BROKEN-WEB", encoding="utf-8")
(APP / "web" / "version.json").write_text(json.dumps({"web": "bad-1"}), encoding="utf-8")
(APP / "web.old").mkdir()
(APP / "web.old" / "index.html").write_text("GOOD-WEB", encoding="utf-8")
(APP / "boot.json").write_text(json.dumps({"web": "bad-1", "ok": False, "bad": [], "at": 0}),
                               encoding="utf-8")

updater.BOOT_WATCH_S = 1.0     # 测试里把 30 秒压到 1 秒（看门狗在调用时才读它）

url2 = android_boot.start(str(APP), str(DIST))
check("坏的那份被挪走（web.broken-*）", bool(bad_files()), str(bad_files()))
check("撤回的是上一版（web.old → web）", (APP / "web" / "index.html").read_text(encoding="utf-8") == "GOOD-WEB")
check("web.old 已经交出去（不再留一份）", not (APP / "web.old").exists())
code, body = get(url2)
check("页面当场就是上一版（没有白屏那一下）", body == "GOOD-WEB", f"code={code} body={body[:20]!r}")
st = state()
check("这次这份覆盖层记了一笔「等报到」（ok=null）", st.get("ok", "missing") is None, json.dumps(st)[:80])
check("坏的那版记进名单（以后不再装它）", "bad-1" in (st.get("bad") or []))

# ---------------------------------------------------------------- ④ 前端来报到了
print("\n④ 前端真来报到 → 看门狗不该把它记成坏的", flush=True)
updater.notify_booted()
check("报到之后 ok=True", state().get("ok") is True)
updater.boot_watchdog()        # 1 秒版，直接跑完（阻塞）
check("报到过的不会被看门狗改判", state().get("ok") is True, json.dumps(state())[:80])

# ---------------------------------------------------------------- ⑤ 没人报到
print("\n⑤ 没人报到 → 看门狗记一笔「没起来」", flush=True)
(APP / "boot.json").write_text(json.dumps({"web": "", "ok": None, "bad": []}), encoding="utf-8")
updater.boot_watchdog()
check("没人报到就被记成 ok=false（下次开窗会撤掉这份前端）", state().get("ok") is False,
      json.dumps(state())[:80])

shutil.rmtree(TMP, ignore_errors=True)
print()
print("结果:", FAILS if FAILS else "无 —— 全部通过")
sys.exit(1 if FAILS else 0)