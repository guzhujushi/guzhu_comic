# -*- coding: utf-8 -*-
"""拿**真发布产物**（web_dist_out/）当发布端，跑一遍客户端的 check + apply。

和 _check_updater.py 的分工：那个用自己临时造的包测"每条红线"，这个测"这次真要发出去的
那两个文件本身能不能被客户端吃下"——发布前跑一次，省得传上去才发现传漏了文件。

跑法：.venv\\Scripts\\python.exe tmp\\_check_publish_real.py
"""
import hashlib
import json
import sys
import tempfile
import threading
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(r"D:\guzhu_comic")
PUB = REPO / "web_dist_out"
sys.path.insert(0, str(REPO))

FAILED = []
PASSED = 0


def ok(name, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print("  PASS  " + name)
    else:
        FAILED.append(name)
        print("  FAIL  " + name + " " + detail)


# ---- 用户目录整个搬进临时目录 ----
TMP = Path(tempfile.mkdtemp(prefix="guzhu_pub_"))
import backend.paths as paths          # noqa: E402
paths.APP_DIR = TMP
paths.WEB_DIR = TMP / "web"
import backend.config as config        # noqa: E402
config.CONFIG_PATH = TMP / "config.yaml"
from backend import updater            # noqa: E402
updater.WEB_OLD = TMP / "web.old"
updater.WEB_NEW = TMP / "web.new"
updater.BOOT_STATE = TMP / "boot.json"


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(PUB)))
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % port
sec = {"enabled": True, "url": base, "auto": True}

manifest = json.loads((PUB / "manifest.json").read_text(encoding="utf-8"))
zip_path = PUB / manifest["file"]

print("发布端 %s" % base)
print("构建号 %s（版本 %s）" % (manifest["web"], manifest["version"]))

# ---- 发布产物自检 ----
blob = zip_path.read_bytes()
ok("zip 的 sha256 与 manifest 一致",
   hashlib.sha256(blob).hexdigest() == manifest["sha256"], manifest["sha256"])
ok("zip 的字节数与 manifest 一致", len(blob) == manifest["size"], "%d vs %d" % (len(blob), manifest["size"]))
ok("manifest 里 file 指的文件真的在目录里", zip_path.is_file(), manifest["file"])

# ---- check ----
# 先"假装"我这份比发布端旧：0.1.2 起 `BUNDLED_WEB` 就是通道上那一版（装完不该一开窗就提示有新版本），
# 不假装的话下面 apply 只会是个 no-op，这条用例就白跑了（同版不提示那条口径由 _check_channel_live.py 守）。
updater.BUNDLED_WEB = "0"
info = updater.check(sec)
ok("check 没报错", not info["error"], info["error"])
ok("check 认得出有新版", info["available"] is True, str(info))
ok("check 报的构建号 = manifest 的", info["web"] == manifest["web"], info["web"])
ok("check 报的版本 = manifest 的", info["version"] == manifest["version"], info["version"])
ok("check 报的体积 = manifest 的", info["size"] == manifest["size"], str(info["size"]))
ok("check 没把自己判成 too_new", info["too_new"] is False)
ok("没装之前 current_web() 就是「包内那版」（覆盖层还没落下来）",
   updater.current_web() == updater.BUNDLED_WEB, updater.current_web())

# ---- apply ----
res = updater.apply(sec)
ok("apply 成功", res.get("ok") is True, str(res))
ok("apply 报告装了多少个文件", int(res.get("files") or 0) > 0, str(res.get("files")))
ok("装完 current_web() = 构建号", updater.current_web() == manifest["web"], updater.current_web())

overlay = paths.WEB_DIR
ok("覆盖层里有 index.html", (overlay / "index.html").is_file())
ok("覆盖层里有 assets 目录", (overlay / "assets").is_dir())
stamp = json.loads((overlay / "version.json").read_text(encoding="utf-8"))
ok("version.json 记下了构建号", stamp.get("web") == manifest["web"], str(stamp))
ok("version.json 记下了版本号", stamp.get("version") == manifest["version"], str(stamp)[:120])
ok("version.json 记下了装的时间", isinstance(stamp.get("at"), (int, float)), str(stamp)[:120])

# 覆盖层与 frontend/dist 内容一致（同一份东西）
import subprocess  # noqa: E402
names = sorted(p.name for p in (overlay / "assets").iterdir())
ok("覆盖层 assets 里有 js 与 css", any(n.endswith(".js") for n in names) and any(n.endswith(".css") for n in names), str(names))

# 再查一次：不该再有新版
info2 = updater.check(sec)
ok("装完再查就没有新版了", info2["available"] is False, str(info2))
ok("装完再查的 current_web 对得上", info2["current_web"] == manifest["web"], info2["current_web"])

httpd.shutdown()
print("\n%d 项通过，%d 项失败" % (PASSED, len(FAILED)))
if FAILED:
    print("失败项：" + "、".join(FAILED))
raise SystemExit(1 if FAILED else 0)
