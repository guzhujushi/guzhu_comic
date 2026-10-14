# -*- coding: utf-8 -*-
r"""按 sha256 查 VirusTotal 已有报告（不上传、不占上传额度）。

跑法：.venv\Scripts\python.exe tmp\_vt_query.py [sha256 ...]
     不给参数就用 build_out 里那两个产物自己算。
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROXY = "http://127.0.0.1:7890"
API = "https://www.virustotal.com/api/v3"
FILES = [ROOT / "build_out" / "GuzhuComic" / "GuzhuComic.exe",
         ROOT / "build_out" / "GuzhuComic-0.1.0-win64.zip"]
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    key = (os.environ.get("VIRUSTOTAL_API_KEY") or "").strip()
    if not key:
        raise SystemExit("环境变量里没有 VIRUSTOTAL_API_KEY")
    jobs = [(p.name, a) for a, p in zip(sys.argv[1:], [])] or []
    if sys.argv[1:]:
        jobs = [("(命令行给的值)", a) for a in sys.argv[1:]]
    else:
        jobs = [(p.name, sha256(p)) for p in FILES]

    for name, digest in jobs:
        req = urllib.request.Request(API + "/files/" + digest, headers={"x-apikey": key})
        try:
            with OPENER.open(req, timeout=60) as r:
                attrs = json.loads(r.read().decode("utf-8"))["data"]["attributes"]
        except urllib.error.HTTPError as e:
            print("%-34s %s -> HTTP %s（还没出报告？）" % (name, digest[:16], e.code))
            continue
        stats = attrs["last_analysis_stats"]
        res = attrs["last_analysis_results"]
        cats = {}
        for r_ in res.values():
            cats[r_["category"]] = cats.get(r_["category"], 0) + 1
        print("\n== %s  sha256=%s" % (name, digest))
        print("   分类：%s" % json.dumps(cats, ensure_ascii=False))
        print("   参与引擎 %d：恶意 %s / 可疑 %s" % (
            len(res), stats.get("malicious", 0), stats.get("suspicious", 0)))
        for eng, r_ in sorted(res.items()):
            if r_["category"] in ("malicious", "suspicious"):
                print("     %-22s %s" % (eng, r_["result"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
