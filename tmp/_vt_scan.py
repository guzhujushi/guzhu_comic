# -*- coding: utf-8 -*-
r"""把出包产物交给 VirusTotal（70+ 引擎）看一眼。

  * 直连不通（Google 被墙），一律走 http://127.0.0.1:7890；
  * 先用 sha256 查已有报告（不占上传额度），查不到再上传；
  * **上传 = 把样本共享给杀软厂商，撤不回来**。

key 从环境变量 VIRUSTOTAL_API_KEY 取（不落盘、不打印）。
跑法：.venv\Scripts\python.exe tmp\_vt_scan.py [文件…]
      默认 = build_out 里的 exe + zip。
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROXY = "http://127.0.0.1:7890"
API = "https://www.virustotal.com/api/v3"
SAVE = ROOT / "tmp" / "_vt"
DEFAULT = [
    ROOT / "build_out" / "GuzhuComic" / "GuzhuComic.exe",
    ROOT / "build_out" / "GuzhuComic-0.1.0-win64.zip",
]


def api_key() -> str:
    key = os.environ.get("VIRUSTOTAL_API_KEY") or os.environ.get("VT_API_KEY") or ""
    if not key.strip():
        raise SystemExit("环境变量里没有 VIRUSTOTAL_API_KEY")
    return key.strip()


OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def call(url, data=None, headers=None, method=None, timeout=180):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with OPENER.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw[:500]}
    except Exception as e:
        return None, {"error": repr(e)}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def upload(path: Path, key: str):
    boundary = "----guzhu" + os.urandom(8).hex()
    body = b"".join([
        b"--" + boundary.encode() + b"\r\n",
        b'Content-Disposition: form-data; name="file"; filename="' + path.name.encode() + b'"\r\n',
        b"Content-Type: application/octet-stream\r\n\r\n",
        path.read_bytes(),
        b"\r\n--" + boundary.encode() + b"--\r\n",
    ])
    headers = {"x-apikey": key,
               "Content-Type": "multipart/form-data; boundary=" + boundary}
    return call(API + "/files", data=body, headers=headers, method="POST")


def wait_analysis(analysis_id: str, key: str, limit_s: int = 900):
    """轮询分析结果；免费额度 4 次/分，所以每 15 秒看一眼"""
    deadline = time.time() + limit_s
    while time.time() < deadline:
        status, data = call(API + "/analyses/" + analysis_id, headers={"x-apikey": key})
        if status == 200:
            state = data.get("data", {}).get("attributes", {}).get("status")
            if state == "completed":
                return data
            print("      …引擎还在跑（status=%s）" % state, flush=True)
        elif status == 429:
            print("      …被限流了（4 次/分），等一会儿再看", flush=True)
        else:
            print("      查询分析状态失败：HTTP %s %s" % (status, str(data)[:160]), flush=True)
        time.sleep(15)
    return None


def report(attrs: dict) -> dict:
    stats = attrs.get("last_analysis_stats") or attrs.get("stats") or {}
    results = attrs.get("last_analysis_results") or attrs.get("results") or {}
    hits = sorted(
        (eng, r.get("result"), r.get("category"))
        for eng, r in results.items()
        if r.get("category") == "malicious" or r.get("category") == "suspicious")
    return {"stats": stats, "hits": hits, "total": len(results)}


def show(name: str, rep: dict) -> None:
    stats = rep["stats"]
    print("      引擎判定：%d 家参与，恶意 %s / 可疑 %s / 无检出 %s" % (
        rep["total"], stats.get("malicious", 0), stats.get("suspicious", 0),
        stats.get("undetected", 0)), flush=True)
    if not rep["hits"]:
        print("      ✓ 没有任何引擎报毒", flush=True)
        return
    for eng, what, cat in rep["hits"]:
        print("      ⚠ %-24s %-10s %s" % (eng, cat, what), flush=True)


def main() -> int:
    key = api_key()
    files = [Path(a) for a in sys.argv[1:]] or DEFAULT
    SAVE.mkdir(parents=True, exist_ok=True)
    bad = 0

    print("走代理 %s｜上传即共享样本给厂商，撤不回来" % PROXY, flush=True)
    for i, path in enumerate(files):
        print("\n== %s（%.1f MB）" % (path.name, path.stat().st_size / 1024 / 1024), flush=True)
        digest = sha256(path)
        print("   sha256 %s" % digest, flush=True)

        status, data = call(API + "/files/" + digest, headers={"x-apikey": key})
        if status == 200:
            print("   已有报告（这次没上传）", flush=True)
        elif status == 404:
            print("   库里没有，上传 …", flush=True)
            if i:
                time.sleep(20)          # 免费额度：4 次/分
            status, data = upload(path, key)
            if status not in (200, 201, 202):
                print("   ✗ 上传失败：HTTP %s %s" % (status, str(data)[:300]), flush=True)
                bad += 1
                continue
            analysis_id = data.get("data", {}).get("id")
            print("   已上传，analysis=%s，等引擎跑完 …" % analysis_id, flush=True)
            data = wait_analysis(analysis_id, key)
            if data is None:
                print("   ✗ 等超时了，稍后自己看：https://www.virustotal.com/gui/file/%s" % digest, flush=True)
                bad += 1
                continue
        else:
            print("   ✗ 查询失败：HTTP %s %s" % (status, str(data)[:300]), flush=True)
            bad += 1
            continue

        attrs = data.get("data", {}).get("attributes", {})
        rep = report(attrs)
        show(path.name, rep)
        (SAVE / (path.name + ".json")).write_text(
            json.dumps({"sha256": digest, "stats": rep["stats"], "hits": rep["hits"]},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print("   报告存到 %s" % (SAVE / (path.name + ".json")), flush=True)

    print("\n完成：%s" % ("全部拿到结果" if not bad else "有 %d 项没拿到，见上面" % bad), flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
