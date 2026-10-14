# -*- coding: utf-8 -*-
r"""打包态验收：真 exe 的本地服务必须只认本机回环 Host（挡 DNS rebinding）。

直连 http://127.0.0.1:<port> 换不同的 Host 头打同一台服务：
  - Host: 127.0.0.1:<port> / localhost:<port>  -> 200（正常用）
  - Host: evil.test                            -> 403（rebinding 走不通）
不带 Host（HTTP/1.0 口径）放行，这条也一起验。

跑法：.venv/Scripts/python.exe tmp/_check_exe_host.py
"""
import http.client
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("D:/guzhu_comic")
EXE = ROOT / "build_out" / "GuzhuComic" / "GuzhuComic.exe"
PORTS = list(range(47753, 47761))


def port_open(port, timeout=0.5):
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def req(port, path, host):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
        if host is not None:
            conn.putheader("Host", host)
        conn.endheaders()
        r = conn.getresponse()
        body = r.read()
        return r.status, body
    finally:
        conn.close()


def main():
    if not EXE.exists():
        print("FAIL  没找到 exe：" + str(EXE), flush=True)
        return False
    busy = [p for p in PORTS if port_open(p)]
    if busy:
        print("FAIL  端口已被占（可能是你开着的那个实例）：" + str(busy) + "，先关掉再跑", flush=True)
        return False

    proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    port = None
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            print("FAIL  exe 自己退了，退出码 " + str(proc.returncode), flush=True)
            return False
        for cand in PORTS:
            if port_open(cand):
                port = cand
                break
        if port:
            break
        time.sleep(0.5)
    if not port:
        print("FAIL  60 秒内本地服务没起来", flush=True)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return False
    print("[check] exe pid=%d 本地服务 :%d" % (proc.pid, port), flush=True)

    ok = True
    cases = [
        ("Host: 127.0.0.1:%d" % port, port, "/index.html", "127.0.0.1:%d" % port, 200),
        ("Host: localhost:%d" % port, port, "/index.html", "localhost:%d" % port, 200),
        ("Host: [::1]:%d" % port, port, "/index.html", "[::1]:%d" % port, 200),
        ("Host: evil.test", port, "/index.html", "evil.test", 403),
        ("Host: evil.test 且要取图", port, "/images/1/00001.webp", "evil.test", 403),
        ("Host: 127.0.0.1.evil.test", port, "/index.html", "127.0.0.1.evil.test", 403),
        ("Host: my.localhost", port, "/index.html", "my.localhost", 403),
        ("不带 Host", port, "/index.html", None, 200),
    ]
    for name, pt, path, host, want in cases:
        try:
            status, body = req(pt, path, host)
        except Exception as e:
            print("FAIL  %-32s 请求炸了 %r" % (name, e), flush=True)
            ok = False
            continue
        flag = "PASS" if status == want else "FAIL"
        print("%s  %-32s -> %d（期望 %d，%d B）" % (flag, name, status, want, len(body)), flush=True)
        if status != want:
            ok = False

    try:
        status, body = req(port, "/index.html", "127.0.0.1:%d" % port)
        if b"<div id=\"app\">" not in body and b"id=\"app\"" not in body:
            print("FAIL  200 拿到的东西不是包内 dist 的 index.html", flush=True)
            ok = False
    except Exception as e:
        print("FAIL  正常 Host 取 index.html 炸了 %r" % e, flush=True)
        ok = False

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True)
    print("\n=> " + ("全部通过" if ok else "有问题，见上面的 FAIL"), flush=True)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
