# -*- coding: utf-8 -*-
"""P1：解扰层的回归检查。

三件事：
  1. `band_plan` 必须是一组**完整的置换**（目标覆盖 0..h-1、源也覆盖 0..h-1，不重不漏）；
  2. 真图对拍：我们的产物与 jmcomic `decode_and_save` 的产物**逐字节相同**
     （桌面替掉 jmcomic 自带解码之后，缓存文件一个字节都不该变）；
  3. `num_for` 与 jmcomic 的口径一致，`.gif` 一律 0；num<=0 时原样不动。

跑法：python tmp/_check_descramble.py   （要连图源，约 30 秒）
"""
import io
import sys
import tempfile
from pathlib import Path

REPO = Path(r"D:\guzhu_comic")
sys.path.insert(0, str(REPO))

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


# 先把"用户目录"搬走，一个真库都不碰
TMP = Path(tempfile.mkdtemp(prefix="guzhu_descramble_"))
import backend.paths as paths
paths.APP_DIR = TMP
paths.DATA_DIR = TMP / "data"
paths.DATA_DB = paths.DATA_DIR / "app.db"
paths.CACHE_DIR = TMP / "cache"
paths.CACHE_DB = paths.CACHE_DIR / "cache.db"
paths.IMG_DIR = paths.CACHE_DIR / "images"
paths.WEBVIEW_DIR = TMP / "webview"
paths.WEB_DIR = TMP / "web"
import backend.config as config
config.CONFIG_PATH = TMP / "config.yaml"
import backend.api as api_mod
api_mod.APP_DIR = TMP
api_mod.DATA_DIR = paths.DATA_DIR
api_mod.DATA_DB = paths.DATA_DB
api_mod.CACHE_DIR = paths.CACHE_DIR
api_mod.CACHE_DB = paths.CACHE_DB
api_mod.IMG_DIR = paths.IMG_DIR
from backend import descramble
from backend.api import API

print("== 1. band_plan 是完整置换 ==")
def tiled(spans, height):
    """这些 (起点, 终点) 是不是严丝合缝拼出 [0, height)：不重不漏、连续"""
    cur = 0
    for start, end in sorted(spans):
        if start != cur or end <= start:
            return False
        cur = end
    return cur == height


bad = []
for h, num in ((1600, 16), (1600, 10), (1000, 3), (999, 8), (1600, 2), (2500, 20), (7, 3)):
    plan = descramble.band_plan(h, num)
    dst = [(y_dst, y_dst + hh) for _, hh, y_dst in plan]
    src = [(y_src, y_src + hh) for y_src, hh, _ in plan]
    if not (tiled(dst, h) and tiled(src, h)):
        bad.append((h, num, sorted(dst), sorted(src)))
ok("各种 (h, num) 下，源与目标都严丝合缝铺满整页", not bad, f"→ {bad[:1]}")
ok("num<=0 / num>h 给空表（=原样放行）",
   descramble.band_plan(1600, 0) == [] and descramble.band_plan(1600, -1) == []
   and descramble.band_plan(4, 8) == [])
ok("over==0 时就是纯倒序", descramble.band_plan(100, 10)[1] == (80, 10, 10))

print("\n== 2. num_for 的口径 ==")
from jmcomic import JmImageTool


class FakeImg:
    img_file_suffix = ".webp"

    def __init__(self, aid, sid, name, suffix=".webp"):
        self.aid = aid
        self.scramble_id = sid
        self.img_file_name = name
        self.img_file_suffix = suffix

    @property
    def is_gif(self):
        return self.img_file_suffix == ".gif"


f = FakeImg("305124", "220980", "00001")
ok("跟 jmcomic 的 get_num_by_detail 一致",
   descramble.num_for(f) == JmImageTool.get_num_by_detail(f) == 16,
   f"→ {descramble.num_for(f)}")
ok(".gif 一律 0（jmcomic 自己也不解 gif）",
   descramble.num_for(FakeImg("305124", "220980", "00001", ".gif")) == 0)
ok("老本子（aid < scramble_id）是 0", descramble.num_for(FakeImg("100000", "220980", "00001")) == 0)

print("\n== 3. 拿真图跟 jmcomic 逐字节对拍 ==")
api = API()
api._download_dir = TMP / "downloads"
api._download_dir.mkdir(parents=True, exist_ok=True)
api._warm_client()
client = api._jm
downloaded = 0
for album, count in (("305124", 2), ("644911", 2), ("422866", 2)):
    try:
        photo = client.get_photo_detail(album)
    except Exception as e:
        print(f"  SKIP  {album} 取不到详情（{type(e).__name__}: {e}）")
        continue
    for img in photo[:count]:
        num = descramble.num_for(img)
        mine = TMP / f"{album}_{img.filename}"
        theirs = TMP / f"{album}_{img.filename}"
        theirs = theirs.with_name(theirs.stem + ".jm" + theirs.suffix)
        try:
            client.download_by_image_detail(img, str(mine), decode_image=False)   # 我们：先落原图
            descramble.fix_file(mine, num)
            client.download_by_image_detail(img, str(theirs))                     # jmcomic：自带解码
        except Exception as e:
            ok(f"{album}/{img.filename} 下载", False, f"→ {type(e).__name__}: {e}")
            continue
        a, b = mine.read_bytes(), theirs.read_bytes()
        ok(f"{album}/{img.filename}（num={num}）与 jmcomic 产物逐字节相同", a == b,
           f"→ 我们 {len(a)} B / jmcomic {len(b)} B")
        downloaded += 1
ok("至少真跑成功了一张（不是全 SKIP）", downloaded > 0, f"→ {downloaded} 张")

print("\n== 4. 走真实下载链路（get_chapter → 后台下载 → 落盘）==")


def wait_for(folder, want, timeout=120.0):
    import time as _t
    t0 = _t.time()
    while _t.time() - t0 < timeout:
        have = [f for f in folder.glob("*") if f.is_file()]
        if len(have) >= want:
            return sorted(have)
        _t.sleep(1.0)
    return sorted(f for f in folder.glob("*") if f.is_file())


import time as _time
CH = "422866"
t0 = _time.time()
ch = api.get_chapter(CH)
ok(f"get_chapter({CH}) 给出图片地址", len(ch["images"]) > 0, f"→ {len(ch['images'])} 张")
folder = paths.IMG_DIR / CH
files = wait_for(folder, 2, timeout=90.0)
ok(f"后台下载真的落盘（{len(files)} 个文件，{_time.time() - t0:.0f}s）", len(files) >= 2,
   f"→ 只有 {[f.name for f in files]}")

# 落盘的那张要是**解扰后**的：拿它跟 jmcomic 的产物比（同尺寸下逐像素差应当极小）
if len(files) >= 1:
    from PIL import Image
    import math
    landed = files[0]
    img0 = client.get_photo_detail(CH)[0]
    want = TMP / "landed_oracle.webp"
    client.download_by_image_detail(img0, str(want))
    a = Image.open(landed).convert("RGB")
    b = Image.open(want).convert("RGB")
    if a.size != b.size:
        ok("落盘文件的尺寸对得上", False, f"→ {a.size} vs {b.size}")
    else:
        # 我们是解扰后重编一遍（有损），所以不比字节；比"整条带错位"这种量级的差异
        step = max(1, a.size[1] // 200)
        diff = 0.0
        n = 0
        for y in range(0, a.size[1], step):
            for x in range(0, a.size[0], 40):
                pa, pb = a.getpixel((x, y)), b.getpixel((x, y))
                diff += sum(abs(pa[i] - pb[i]) for i in range(3)) / 3
                n += 1
        mad = diff / max(1, n)
        ok("落盘的图与「解扰后」一致（条带没错位）", mad < 12.0,
           f"→ 平均每个采样点差 {mad:.1f}（错位的话会到 60 以上）")

print("\n== 5. num<=0 原样不动 ==")
probe = TMP / "untouched.webp"
if downloaded:
    src = next(TMP.glob("*.webp"))
    probe.write_bytes(src.read_bytes())
    before = probe.read_bytes()
    descramble.fix_file(probe, 0)
    ok("num=0 → 文件一个字节不变", probe.read_bytes() == before)

print(f"\n结果：{PASSED} 通过 / {len(FAILED)} 失败")
if FAILED:
    print("失败项：" + "；".join(FAILED))
sys.exit(1 if FAILED else 0)
