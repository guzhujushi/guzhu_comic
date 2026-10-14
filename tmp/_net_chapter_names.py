# -*- coding: utf-8 -*-
r"""真图源端到端：走 API 的正常路径，确认"文件名收口"没把正常名字改坏。

跑法：.venv\Scripts\python.exe tmp\_net_chapter_names.py
"""
import os
import sys
import time
from pathlib import Path

for k in list(os.environ):
    if k.lower() in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy"):
        del os.environ[k]
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import api as apimod          # noqa: E402
from backend.paths import IMG_DIR          # noqa: E402

PHOTO = "209828"

api = apimod.API()
client = api._jm
t0 = time.time()
photo = client.get_photo_detail(PHOTO)
raw = [img.filename for img in photo]
safe = [apimod._img_name(img) for img in photo]
print("详情 OK：%s 共 %d 张（%.1fs）" % (photo.photo_id, len(photo), time.time() - t0), flush=True)
print("前 5 张原始名：", raw[:5], flush=True)
print("前 5 张收口后：", safe[:5], flush=True)

changed = [i for i, (a, b) in enumerate(zip(raw, safe)) if a != b]
print("被改动的张数：%d（正常数据应当是 0）" % len(changed), flush=True)
if changed:
    for i in changed[:5]:
        print("   #%d %r -> %r" % (i + 1, raw[i], safe[i]), flush=True)

out = api.get_chapter(PHOTO)
names = [Path(str(x)).name for x in out.get("images", [])]
print("get_chapter 返回 %d 张，头两张 %s" % (len(names), names[:2]), flush=True)

folder = IMG_DIR / PHOTO
deadline = time.time() + 20
while time.time() < deadline:
    got = sorted(p.name for p in folder.glob("*") if p.is_file())
    if got:
        break
    time.sleep(0.5)
print("缓存目录里的文件（前 5 个）：", got[:5], flush=True)

ok = (not changed) and len(names) == len(raw) and bool(got) and all(not n.startswith("..") for n in got)
print()
print("结果:", "全部通过" if ok else "有问题，见上面")
sys.exit(0 if ok else 1)
