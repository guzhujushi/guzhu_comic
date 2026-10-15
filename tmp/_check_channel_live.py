# -*- coding: utf-8 -*-
"""对着**线上更新通道**跑一遍客户端的 check + apply（临时 HOME，不碰真数据）。

和 _check_publish_real.py 的分工：
  * _check_publish_real.py —— 发布**之前**，拿 web_dist_out 里那两个产物起本地服务自检；
  * 这个 —— 发布**之后**，拿真地址真网络真 TLS 走一遍，确认通道真的通了（顺便证明不用代理）。

2026-10-15 改过一处口径：官方包从 0.1.2 起把 `BUNDLED_WEB` 钉成通道上那一版（装完不该一开窗就提示
"有新版本"），所以这里先按真实构建号验"同版就不提示"，再**假装**自己比线上旧（`BUNDLED_WEB = "0"`）
把真下载 / 真解压 / 真换目录走一遍 —— 否则 apply 只会是个 no-op，这条就白跑了。

跑法：.venv\\Scripts\\python.exe tmp\\_check_channel_live.py
"""
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(r"D:\guzhu_comic")
URL = "https://code.guzhujushi.cn/guzhujushi/guzhu_comic/raw/branch/main/web"
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


TMP = Path(tempfile.mkdtemp(prefix="guzhu_live_"))
import backend.paths as paths          # noqa: E402
paths.APP_DIR = TMP
paths.WEB_DIR = TMP / "web"
import backend.config as config        # noqa: E402
config.CONFIG_PATH = TMP / "config.yaml"
from backend import updater            # noqa: E402
updater.WEB_OLD = TMP / "web.old"
updater.WEB_NEW = TMP / "web.new"
updater.BOOT_STATE = TMP / "boot.json"

sec = {"enabled": True, "url": URL, "auto": True}
print("通道地址 " + URL)

# 1) 裸 HTTP 拉 manifest（不经过 updater 的兜底逻辑，看的就是"最朴素那次请求"）
with urllib.request.urlopen(URL + "/manifest.json", timeout=20) as r:
    raw = r.read()
manifest = json.loads(raw.decode("utf-8"))
print("线上构建号 %s（版本 %s）" % (manifest["web"], manifest["version"]))
ok("匿名 https 能拉到 manifest", isinstance(manifest, dict) and bool(manifest.get("web")))

# 2) 裸下载 zip 并核 sha256（证明产物真的能匿名下载、字节没坏）
with urllib.request.urlopen("%s/%s" % (URL, manifest["file"]), timeout=60) as r:
    blob = r.read()
ok("匿名能下载 zip", len(blob) == manifest["size"],
   "%d vs %s" % (len(blob), manifest["size"]))
ok("下载回来的 zip sha256 与 manifest 一致",
   hashlib.sha256(blob).hexdigest() == manifest["sha256"], manifest["sha256"])

# 3) 走客户端的 check()
info = updater.check(sec)
ok("check 没报错（这条同时证明不需要代理）", not info["error"], info["error"])
# "同版就不该提示有新版" 从 0.1.2 起是**正常状态**（包内那份就是通道上那一版）
same_as_channel = (updater.BUNDLED_WEB == manifest["web"])
ok("包内与线上同版 → 不提示有新版（装完一开窗不该弹「有新版本」）" if same_as_channel
   else "check 认得出有新版",
   info["available"] is (not same_as_channel),
   "BUNDLED_WEB=%s available=%s" % (updater.BUNDLED_WEB, info["available"]))
ok("check 报的构建号 = 线上 manifest 的", info["web"] == manifest["web"], info["web"])
ok("check 报的 notes 与线上一致", info["notes"] == manifest["notes"], info["notes"][:60])
ok("check 的 app_min 不卡我（0.1.1）", info["too_new"] is False and info["app_min"] == "0.1.1")

# 4) 走客户端的 apply() —— 先"假装"我这份比线上旧，好让真下载 / 真解压 / 真换目录都跑一遍
updater.BUNDLED_WEB = "0"
res = updater.apply(sec)
ok("apply 成功", res.get("ok") is True, str(res))
ok("装完 current_web() = 线上构建号", updater.current_web() == manifest["web"], updater.current_web())
overlay = paths.WEB_DIR
ok("覆盖层里有 index.html", (overlay / "index.html").is_file())
ok("覆盖层里有 assets", (overlay / "assets").is_dir())
stamp = json.loads((overlay / "version.json").read_text(encoding="utf-8"))
ok("version.json 记下构建号与版本", stamp.get("web") == manifest["web"] and stamp.get("version") == manifest["version"],
   str(stamp))
ok("首次安装：原来没有覆盖层，不该凭空造出 web.old（符合 _swap 的设计）",
   not (TMP / "web.old").exists())

# 5) 装完再查
info2 = updater.check(sec)
ok("装完再查就没有新版了", info2["available"] is False, str(info2))

print("\n%d 项通过，%d 项失败" % (PASSED, len(FAILED)))
if FAILED:
    print("失败项：" + "、".join(FAILED))
raise SystemExit(1 if FAILED else 0)
