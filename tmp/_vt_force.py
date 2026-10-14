# -*- coding: utf-8 -*-
r"""强制让 VirusTotal 重新分析（不重新上传），再看一遍判定。

用在"想确认某个引擎的判定是否稳定"时（免费额度 4 次/分，别频繁踢）。

跑法：.venv\Scripts\python.exe tmp/_vt_force.py <sha256> [等待秒数]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

PROXY = "http://127.0.0.1:7890"
API = "https://www.virustotal.com/api/v3"
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def call(url, method=None, timeout=60):
    key = (os.environ.get("VIRUSTOTAL_API_KEY") or "").strip()
    req = urllib.request.Request(url, headers={"x-apikey": key}, method=method)
    try:
        with OPENER.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw[:300]}


def main():
    digest = sys.argv[1]
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    status, data = call(API + "/files/" + digest + "/analyse", method="POST")
    print("触发重新分析 HTTP %s %s" % (status, str(data)[:200]), flush=True)
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(30)
        status, data = call(API + "/files/" + digest)
        if status != 200:
            print("  查询失败 HTTP %s" % status, flush=True)
            continue
        a = data["data"]["attributes"]
        stats = a.get("last_analysis_stats") or {}
        results = a.get("last_analysis_results") or {}
        hits = sorted((e, r.get("result")) for e, r in results.items()
                      if r.get("category") in ("malicious", "suspicious"))
        print("  时间 %s｜引擎 %d｜恶意 %s / 无检出 %s" % (
            a.get("last_analysis_date"), len(results), stats.get("malicious"),
            stats.get("undetected")), flush=True)
        for e, what in hits:
            print("     %-22s %s" % (e, what), flush=True)
        if stats.get("malicious") or stats.get("undetected"):
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
