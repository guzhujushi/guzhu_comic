# -*- coding: utf-8 -*-
r"""看某个 sha256 在 VirusTotal 上的分析状态；必要时触发一次重新分析（不重新上传）。

跑法：.venv\Scripts\python.exe tmp\_vt_status.py <sha256> [--analyse] [--wait 秒]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

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


def show(digest):
    status, data = call(API + "/files/" + digest)
    if status != 200:
        print("查询失败 HTTP %s %s" % (status, str(data)[:200]))
        return None
    a = data["data"]["attributes"]
    stats = a.get("last_analysis_stats") or {}
    print("  类型 %s｜大小 %s MB｜提交次数 %s" % (
        a.get("type_description"), round((a.get("size") or 0) / 1048576, 1), a.get("times_submitted")))
    print("  上次分析时间 %s｜引擎统计 %s" % (a.get("last_analysis_date"), json.dumps(stats, ensure_ascii=False)))
    return a


def main():
    digest = sys.argv[1]
    print("== %s" % digest)
    a = show(digest)
    if a is None:
        return 1
    if a.get("last_analysis_stats", {}).get("undetected"):
        print("  已经有引擎判定了，不用等")
        return 0
    if "--analyse" in sys.argv:
        print("  还没有引擎判定 → 触发一次重新分析（不重新上传）")
        status, data = call(API + "/files/" + digest + "/analyse", method="POST")
        print("  触发结果 HTTP %s %s" % (status, str(data)[:160]))
    wait = 0
    if "--wait" in sys.argv:
        wait = int(sys.argv[sys.argv.index("--wait") + 1])
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(30)
        a = show(digest)
        if a and a.get("last_analysis_stats", {}).get("undetected"):
            print("  分析完成")
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
