# -*- coding: utf-8 -*-
r"""核对本地图片静态服务：目录列表关掉了，正常取图照旧，路径穿越出不去。"""
import functools
import http.server
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.api import _QuietHandler   # noqa: E402

FAILS = []
tmp = Path(tempfile.mkdtemp(prefix="gz_img_"))
cache = tmp / "cache"
dl = tmp / "downloads"
(cache / "sub").mkdir(parents=True)
(cache / "sub" / "a.jpg").write_bytes(b"IMG")
(cache / "root.jpg").write_bytes(b"ROOT")
outside = tmp / "secret.txt"
outside.write_text("SECRET", encoding="utf-8")
(dl / "422866" / "530000").mkdir(parents=True)
(dl / "422866" / "530000" / "1.jpg").write_bytes(b"DL")


class Handler(_QuietHandler):
    extra_roots = {"/downloads": dl}


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                        functools.partial(Handler, directory=str(cache)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % server.server_address[1]


def get(path):
    try:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:                       # noqa: BLE001
        return repr(e), b""


def check(name, fn):
    try:
        fn()
        print("PASS  " + name)
    except AssertionError as e:
        FAILS.append(name)
        print(f"FAIL  {name}: {e}")


def listing_off():
    for path in ("/", "/sub/", "/sub"):
        code, body = get(path)
        assert code in (403, 404), f"{path} 应被拒，实际 {code}"
        assert b"<title>Directory listing" not in body, f"{path} 不该给出目录列表"


def files_ok():
    code, body = get("/root.jpg")
    assert code == 200 and body == b"ROOT", f"根目录文件取不到：{code}"
    code, body = get("/sub/a.jpg")
    assert code == 200 and body == b"IMG", f"子目录文件取不到：{code}"
    code, body = get("/downloads/422866/530000/1.jpg")
    assert code == 200 and body == b"DL", f"离线副本取不到：{code}"


def no_traversal():
    for path in ("/../secret.txt", "/sub/../../secret.txt", "/..%2fsecret.txt",
                 "/downloads/../secret.txt", "/downloads/../../secret.txt",
                 "/downloads/..%2f..%2fsecret.txt"):
        code, body = get(path)
        assert b"SECRET" not in body, f"{path} 读到了根目录外面的文件！code={code}"


check("目录列表已关闭", listing_off)
check("正常取图不受影响", files_ok)
check("路径穿越出不去", no_traversal)

server.shutdown()
import shutil
shutil.rmtree(tmp, ignore_errors=True)
print()
print("结果:", FAILS if FAILS else "无 —— 全部通过")
sys.exit(1 if FAILS else 0)