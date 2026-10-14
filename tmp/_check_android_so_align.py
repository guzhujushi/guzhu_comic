# -*- coding: utf-8 -*-
r"""安卓 wheel 里的 .so 是不是 16 KB 页对齐（Android 15+ 会以 16 KB 页启动，没对齐 = 加载直接失败）。

为什么要单独有这个检查：pip 上的安卓轮子谁都能发，对齐没对齐只能拆开看。而 4 KB 对齐的 .so
在老设备上一切正常、在新设备上直接起不来 —— 属于"必测但平时想不到"的那类坑。

跑法：.venv\Scripts\python.exe tmp\_check_android_so_align.py <wheel 或 .so 的路径>
      .venv\Scripts\python.exe tmp\_check_android_so_align.py <wheel> --keep   # 顺便列出动态依赖
2026-10-14 实测：curl_cffi-0.16.3-cp314-cp314-android_24_arm64_v8a.whl → min p_align = 0x4000（PASS）
"""
import re
import struct
import sys
import zipfile
from pathlib import Path

PT_LOAD = 1
MACHINES = {0x3E: "x86_64", 0xB7: "aarch64", 0x28: "armv7", 0xF3: "riscv64"}
PAGE_16K = 0x4000


def load_objects(path: Path) -> list[tuple[str, bytes]]:
    """给 wheel（zip）就挑里面所有 .so；给单个 .so 就直接读"""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            return [(n, zf.read(n)) for n in zf.namelist() if n.endswith(".so")]
    return [(path.name, path.read_bytes())]


def check(name: str, data: bytes, show_deps: bool) -> bool:
    if data[:4] != b"\x7fELF":
        print(f"  {name}: 不是 ELF，跳过")
        return True
    if data[4] != 2:
        print(f"  {name}: 32 位 ELF，这里只看 64 位")
        return True

    endian = "<" if data[5] == 1 else ">"
    machine = struct.unpack_from(endian + "H", data, 18)[0]
    # ELF64 头：e_phoff(8) @32, e_shoff(8) @40, e_flags(4) @48, e_ehsize(2) @52,
    #            e_phentsize(2) @54, e_phnum(2) @56
    e_phoff, _e_shoff, _flags, _ehsize, e_phentsize, e_phnum = struct.unpack_from(
        endian + "QQIHHH", data, 32)

    aligns = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, _p_flags, _o, _va, _pa, _fsz, _msz, p_align = struct.unpack_from(
            endian + "IIQQQQQQ", data, off)
        if p_type == PT_LOAD:
            aligns.append(p_align)

    worst = min(aligns) if aligns else 0
    ok = worst >= PAGE_16K
    print(f"  {name}: {len(data) / 1048576:.2f} MB, {MACHINES.get(machine, hex(machine))}, "
          f"{len(aligns)} 个 PT_LOAD, min p_align={hex(worst)} -> "
          + ("PASS 16KB" if ok else "FAIL（只按 4KB 对齐，新设备上加载会失败）"))
    if show_deps:
        deps = sorted({m.decode() for m in re.findall(rb"lib[a-zA-Z0-9_+\-.]*\.so[0-9.]*", data)})
        deps = [d for d in deps if not d.startswith(("libc.so", "libm.so", "libdl.so"))]
        if deps:
            print("      动态依赖: " + ", ".join(deps[:10]))
    return ok


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    show_deps = "--keep" in argv or "--deps" in argv
    if len(args) != 1:
        print(__doc__)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"找不到文件：{path}")
        return 2
    print(path.name)
    all_ok = True
    for name, data in load_objects(path):
        all_ok = check(name, data, show_deps) and all_ok
    print("结论：" + ("全部 16 KB 对齐，Android 15+ 可加载"
                     if all_ok else "存在未对齐的 .so —— Android 15+（16 KB 页）会加载失败"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))