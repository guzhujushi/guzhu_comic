# -*- coding: utf-8 -*-
"""把 tmp/_check_*.py 顺序跑一遍（跳过 exe 那三个：那几支要跑真 exe，慢且与本次改动无关）。"""
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(r"D:\guzhu_comic")
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
# 跳过两类：
#   * exe 那几支：要出包 / 跑真 exe，慢且与多数改动无关；
#   * `_check_android_so_align.py`：它不是"跑一遍就出结论"的检查，是**要传 wheel 路径**的工具
#     （不带参数会打印用法并 exit 2，被当成 FAIL 是误判）
SKIP = {"_check_exe_footprint.py", "_check_exe_host.py", "_check_exe_hotupdate.py",
        "_check_exe_nonascii_path.py", "_check_exe_package.py", "_check_exe_real.py",
        "_check_exe_single.py", "_check_android_so_align.py"}

scripts = sorted(p for p in (ROOT / "tmp").glob("_check_*.py") if p.name not in SKIP)
bad = []
for p in scripts:
    t0 = time.time()
    try:
        r = subprocess.run([PY, str(p)], capture_output=True, timeout=900,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        code = r.returncode
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
    except subprocess.TimeoutExpired:
        code, tail = 124, ["（超时 900s）"]
    tag = "PASS" if code == 0 else "FAIL"
    print("%-6s %-34s %5.1fs  %s" % (tag, p.name, time.time() - t0, tail[0][:90]), flush=True)
    if code != 0:
        bad.append((p.name, code, (r.stdout or "")[-1200:] if code != 124 else ""))

print("\n跑完 %d 支；失败 %d 支" % (len(scripts), len(bad)))
for name, code, out in bad:
    print("\n" + "=" * 30, name, "exit", code, "=" * 30)
    print(out)
sys.exit(1 if bad else 0)