# -*- coding: utf-8 -*-
"""前端热更新通道的回归检查（用完即删）。

真起一个本地 HTTP 服务当"发布端"，真下、真解压、真换目录，把 backend/updater.py 的每条红线
都跑一遍：

  * 正常装上 / 装完 current_web 变了 / 再查就没有新版；
  * sha256 对不上 → 拒；
  * 压缩包里塞 .exe（或任何非白名单后缀）→ 拒；
  * 压缩包里有 `../` 越界路径 → 拒；
  * index.html 引用的 assets 缺文件（发布时传漏了）→ 拒；
  * app_min 比本机安装包高 → 不装（too_new）；
  * 上次那份前端没起来 → 自动退回上一版 / 包内那份（review_boot），并记进 known_bad；
  * 手动 rollback；
  * 地址只认 https（本机 127.0.0.1 的 http 例外）。
"""
import io
import json
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = r"D:\guzhu_comic"
sys.path.insert(0, REPO)

FAILED: list[str] = []
PASSED = 0


def ok(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name} {detail}")


def raises(name: str, fn, want: str = "") -> None:
    try:
        fn()
    except Exception as e:            # noqa: BLE001
        text = str(e)
        ok(name, (want in text) if want else True, f"→ {text}")
        return
    ok(name, False, "→ 居然没报错")


# ---- 把"用户目录"整个搬到临时目录（真库、真配置一个都别碰） ----
TMP = Path(tempfile.mkdtemp(prefix="guzhu_upd_"))
import backend.paths as paths                 # noqa: E402
paths.APP_DIR = TMP
paths.WEB_DIR = TMP / "web"
import backend.config as config               # noqa: E402
config.CONFIG_PATH = TMP / "config.yaml"
from backend import updater                   # noqa: E402
updater.WEB_OLD = TMP / "web.old"
updater.WEB_NEW = TMP / "web.new"
updater.BOOT_STATE = TMP / "boot.json"

# ---- 假发布端：一个临时目录 + 一个本地 HTTP 服务 ----
PUB = TMP / "pub"
PUB.mkdir(parents=True)


def make_zip(name: str, files: dict[str, bytes | str], extra: list[tuple[str, bytes]] | None = None) -> Path:
    path = PUB / name
    with zipfile.ZipFile(path, "w") as zf:
        for rel, data in files.items():
            zf.writestr(rel, data.encode("utf-8") if isinstance(data, str) else data)
        for rel, data in extra or []:
            zf.writestr(rel, data)
    return path


def publish(build: str, *, version: str = "1.0.0", app_min: str = "0.1.0",
            files: dict | None = None, extra: list | None = None,
            sha_override: str | None = None, size_override: int | None = None,
            name: str | None = None) -> dict:
    """造一版前端 + 写 manifest.json（发布端 scripts/publish_frontend.ps1 的等价物）"""
    import hashlib
    name = name or f"frontend-dist-{build}.zip"
    files = files if files is not None else {
        "index.html": '<!doctype html><html><head><link rel="stylesheet" href="/assets/a.css"></head>'
                      '<body><script type="module" src="/assets/a.js"></script></body></html>',
        "assets/a.js": f"console.log('{build}')",
        "assets/a.css": "body{}",
    }
    zip_path = make_zip(name, files, extra)
    raw = zip_path.read_bytes()
    manifest = {
        "version": version, "web": build, "app_min": app_min, "notes": f"构建 {build}",
        "published_at": int(time.time()), "file": name,
        "size": size_override if size_override is not None else len(raw),
        "sha256": sha_override if sha_override is not None else hashlib.sha256(raw).hexdigest(),
    }
    (PUB / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False),
                                       encoding="utf-8", newline="\n")
    return manifest


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


handler = partial(_Quiet, directory=str(PUB))
server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_address[1]}"
SEC = {"enabled": True, "url": BASE, "auto": True}
print(f"假发布端：{BASE}（{PUB}）")

# ---- 1) 正常装上 ----
print("\n[1] 正常更新")
publish("b1")
info = updater.check(SEC)
ok("check: 有新版本", info["available"] and info["web"] == "b1", str(info))
ok("check: 记下版本号", info["version"] == "1.0.0")
res = updater.apply(SEC)
ok("apply: 换了文件", res["changed"] and res["files"] == 3, str(res))
ok("apply: web 目录就是新那份", (paths.WEB_DIR / "index.html").is_file()
   and "b1" in (paths.WEB_DIR / "assets" / "a.js").read_text(encoding="utf-8"))
ok("apply: 写了构建号", updater.current_web() == "b1", updater.current_web())
ok("apply: 静态服务的根跟着换", paths.web_dist_dir() == paths.WEB_DIR)
ok("再查：没有新版了", updater.check(SEC)["available"] is False)
ok("apply: 已经是最新时是空操作", updater.apply(SEC)["changed"] is False)

# ---- 2) sha256 对不上 ----
print("\n[2] 篡改过的包")
publish("b2", sha_override="0" * 64)
raises("sha256 不对 → 拒", lambda: updater.apply(SEC), "sha256")
ok("拒了以后还是原来那份", updater.current_web() == "b1")

# ---- 3) 大小对不上 ----
publish("b3", size_override=1)
raises("大小不对 → 拒", lambda: updater.apply(SEC), "大小")

# ---- 4) 白名单：塞个 exe ----
print("\n[3] 不该有的文件")
publish("b4", extra=[("tool.exe", b"MZ...")])
raises("zip 里有 .exe → 拒", lambda: updater.apply(SEC), "不该有的文件")
publish("b5", extra=[("assets/payload.bat", b"format c:")])
raises("zip 里有 .bat → 拒", lambda: updater.apply(SEC), "不该有的文件")

# ---- 5) 路径穿越 ----
publish("b6", extra=[("../evil.html", b"<html>")])
raises("路径越界 → 拒", lambda: updater.apply(SEC), "不安全的路径")
ok("越界那次没落地", not (TMP / "evil.html").exists() and not (PUB / "evil.html").exists())

# ---- 6) 发布时传漏了文件 ----
publish("b7", files={"index.html": '<script src="/assets/missing.js"></script>',
                     "assets/a.js": "x"})
raises("index.html 引用的文件不在 → 拒", lambda: updater.apply(SEC), "少了文件")

# ---- 7) app_min 比本机高 ----
print("\n[4] 要更新的安装包")
publish("b8", app_min="9.9.9")
info = updater.check(SEC)
ok("too_new 标出来", info["too_new"] and info["available"] is False, str(info))
raises("too_new → 不装", lambda: updater.apply(SEC), "安装包")

# ---- 8) 没起来 → 自动退回 ----
print("\n[5] 装上去没能开起来（自动回滚）")
publish("b9")
updater.apply(SEC)
ok("装上了 b9", updater.current_web() == "b9")
updater.mark_boot()
updater.notify_booted()
ok("报过到以后 review_boot 什么都不做", updater.review_boot()["rolled_back"] is False)

updater.apply(SEC)                       # 再装一次 b9 之前先换个新的
publish("b10")
updater.apply(SEC)
updater.mark_boot()                      # 记下"这次用的是 b10，等它报到"
updater.BOOT_WATCH_S = 0.0               # 不等 30 秒，直接判"没报到"
updater.boot_watchdog()
ok("记成没起来了", json.loads(updater.BOOT_STATE.read_text(encoding="utf-8"))["ok"] is False)
review = updater.review_boot()
ok("自动退回上一版（b9）", review["rolled_back"] and updater.current_web() == "b9", str(review))
ok("上一版还在（没被删）", (paths.WEB_DIR / "assets" / "a.js").read_text(encoding="utf-8").find("b9") >= 0)
bad = updater.check(SEC)
ok("坏的那版记进 known_bad", bad["known_bad"] is True, str(bad))
raises("同一版不再自动重装", lambda: updater.apply(SEC), "上次")

# ---- 9) 手动 rollback ----
print("\n[6] 手动退回")
publish("b11")
updater.apply(SEC)
ok("装上 b11", updater.current_web() == "b11")
back = updater.rollback()
ok("退回上一版", back["ok"] and updater.current_web() == "b9", str(back))
publish("b12")
updater.apply(SEC)
updater.WEB_OLD.rename(TMP / "web.old.moved")     # 模拟"没有上一版"
raises("没有上一版时 rollback 报错", lambda: updater.rollback(), "没有上一版")

# ---- 10) 首次更新（没有 web.old）时坏了 → 退回包内那份 ----
print("\n[7] 第一次更新就坏（没有上一版可退）")
shutil.rmtree(paths.WEB_DIR)
shutil.rmtree(TMP / "web.old.moved", ignore_errors=True)
updater.forget_boot()
publish("b13")
updater.apply(SEC)
updater.mark_boot()
updater.boot_watchdog()
review = updater.review_boot()
ok("退回包内那份", review["rolled_back"] and not paths.WEB_DIR.exists(), str(review))
ok("退回后用的就是包内 dist", paths.web_dist_dir() != paths.WEB_DIR)

# ---- 11) 地址白名单 ----
print("\n[8] 地址")
ok("https 放行", updater._check_url("https://code.guzhujushi.cn/x") == "https://code.guzhujushi.cn/x")
ok("本机 http 放行", updater._check_url("http://127.0.0.1:8000/x").startswith("http://127.0.0.1"))
raises("外部 http → 拒", lambda: updater._check_url("http://example.com/x"), "https")
raises("file:// → 拒", lambda: updater._check_url("file:///C:/x"), "https")
ok("目录地址会补 manifest.json", updater.manifest_url("https://a.com/web").endswith("/web/manifest.json"))
ok("直接给 .json 就用它", updater.manifest_url("https://a.com/web/m.json").endswith("m.json"))

# ---- 12) 通道关着 / 连不上 ----
print("\n[9] 软失败：不许抛异常")
off = updater.check({"enabled": False, "url": BASE})
ok("关着时 error 里写清楚", off["available"] is False and "关着" in off["error"], str(off["error"]))
dead = updater.check({"enabled": True, "url": "http://127.0.0.1:1/x"})
ok("连不上也只是 error", dead["available"] is False and bool(dead["error"]))
(PUB / "manifest.json").write_text("{oops", encoding="utf-8")
broken = updater.check(SEC)
ok("manifest 坏掉也只是 error", broken["available"] is False and "读不懂" in broken["error"])
server.shutdown()

print(f"\n{'=' * 60}\n通过 {PASSED}，失败 {len(FAILED)}")
for name in FAILED:
    print("  -", name)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAILED else 0)
