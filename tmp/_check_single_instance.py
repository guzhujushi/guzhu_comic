# -*- coding: utf-8 -*-
r"""单实例锁的用例：第一个拿到、第二个拿不到、第一个退出后又拿得到。

全程用子进程，父进程自己不抢锁（免得自己被算成"第一个"）。
跑法：.venv\Scripts\python.exe tmp\_check_single_instance.py
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(ROOT))

from backend import single_instance  # noqa: E402

CHILD = (
    "import sys, time\n"
    "sys.path.insert(0, r'%s')\n"
    "from backend.single_instance import acquire\n"
    "ok = acquire()\n"
    "print('ACQUIRED', ok, flush=True)\n"
    "if not ok:\n"
    "    sys.exit(0)        # 真实场景：第二个实例提示完就退，不占着锁\n"
    "time.sleep(20)\n"
) % ROOT

FAILS: list = []


def expect(cond: bool, msg: str) -> None:
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


def start() -> subprocess.Popen:
    return subprocess.Popen([str(PY), "-c", CHILD], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)


def first_line(proc: subprocess.Popen, wait: float = 8.0) -> str:
    deadline = time.time() + wait
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line:
            return line.strip()
    return "<没有输出>"


def main() -> int:
    c1 = start()
    l1 = first_line(c1)
    expect(l1 == "ACQUIRED True", "第一个进程拿到锁（实际 %r）" % l1)

    c2 = start()
    l2 = first_line(c2)
    expect(l2 == "ACQUIRED False", "第一个还活着时，第二个拿不到（实际 %r）" % l2)
    time.sleep(0.5)
    expect(c2.poll() is not None, "拿不到锁的进程应当自己退出（真 exe 就是这个行为）")

    c1.kill()
    c1.wait(timeout=10)
    time.sleep(1.0)
    c3 = start()
    l3 = first_line(c3)
    expect(l3 == "ACQUIRED True", "前一个退出后，新进程又能拿到（实际 %r）" % l3)

    expect(single_instance.focus_existing("这个标题肯定没有") is False,
           "找不到窗口时 focus_existing 返回 False（不抛异常）")

    for p in (c2, c3):
        if p.poll() is None:
            p.kill()
        p.wait(timeout=10)

    print()
    print("结果:", FAILS if FAILS else "全部通过")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
