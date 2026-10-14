# -*- coding: utf-8 -*-
r"""把 VirusTotal 的逐引擎判定拉全（tmp/_vt_scan.py 只存了汇总）。

跑法：.venv\Scripts\python.exe tmp\_vt_detail.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAVE = ROOT / "tmp" / "_vt"
PROXY = "http://127.0.0.1:7890"
API = "https://www.virustotal.com/api/v3"
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
BIG = ("Microsoft", "Kaspersky", "ESET-NOD32", "BitDefender", "Avast", "AVG", "McAfee",
       "Symantec", "TrendMicro", "Sophos", "Fortinet", "Paloalto", "Google", "SentinelOne",
       "CrowdStrike", "Elastic", "Qihoo-360", "Jiangmin", "F-Secure", "Norton", "Malwarebytes")


def main() -> int:
    key = (os.environ.get("VIRUSTOTAL_API_KEY") or "").strip()
    for path in sorted(SAVE.glob("*.json")):
        if path.name.endswith(".full.json"):
            continue
        digest = json.loads(path.read_text(encoding="utf-8"))["sha256"]
        req = urllib.request.Request(API + "/files/" + digest, headers={"x-apikey": key})
        with OPENER.open(req, timeout=120) as r:
            attrs = json.loads(r.read().decode("utf-8"))["data"]["attributes"]
        results = attrs["last_analysis_results"]
        (SAVE / (path.stem + ".full.json")).write_text(
            json.dumps({"sha256": digest, "stats": attrs["last_analysis_stats"],
                        "engines": results}, ensure_ascii=False, indent=2), encoding="utf-8")

        cats = {}
        for r_ in results.values():
            cats[r_["category"]] = cats.get(r_["category"], 0) + 1
        print("\n== %s" % digest[:16])
        print("   %s  sha256=%s" % (path.stem, digest))
        print("   分类统计：" + json.dumps(cats, ensure_ascii=False))
        print("   报了的引擎：")
        for eng, r_ in sorted(results.items()):
            if r_["category"] in ("malicious", "suspicious"):
                print("     %-26s %-10s %s" % (eng, r_["category"], r_["result"]))
        print("   大厂判定：")
        for eng in BIG:
            r_ = results.get(eng)
            if r_:
                print("     %-14s %s" % (eng, r_["result"] or "clean"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
