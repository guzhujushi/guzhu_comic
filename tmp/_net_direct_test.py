# -*- coding: utf-8 -*-
r"""直连可达性测试（**不走任何代理**）：应用真正会连的那些域名在国内网络下通不通。

跑法：.venv/Scripts/python.exe tmp/_net_direct_test.py
"""
import os
import socket
import sys
import time

# 先把自己环境里的代理变量清掉：这一轮要的就是"没有科学上网"的效果
for k in list(os.environ):
    if k.lower() in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy"):
        del os.environ[k]
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

TARGETS = [
    ("域名发现页", "jm365.work", 443),
    ("发布页", "jmcomicgo.org", 443),
    ("API-1", "www.cdngwc.cc", 443),
    ("API-2", "www.cdngwc.club", 443),
    ("API-3", "www.cdngwc.net", 443),
    ("API-4", "www.cdnhjk.net", 443),
    ("图床(已知)", "cdn-msp3.jmapinodeudzn.net", 443),
]


def probe(host, port, tcp_timeout=6.0):
    t0 = time.time()
    try:
        ip = socket.gethostbyname(host)
    except Exception as e:
        return None, ("DNS 失败: %r" % (e,)), 0.0
    try:
        with socket.create_connection((ip, port), timeout=tcp_timeout):
            pass
    except Exception as e:
        return ip, ("TCP 连不上: %r" % (e,)), time.time() - t0
    return ip, "TCP 通", time.time() - t0


def http_probe(host, path="/"):
    """真发一次 HTTPS 请求（不用任何代理），看能不能拿到响应"""
    import urllib.request
    url = "https://%s%s" % (host, path)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    t0 = time.time()
    try:
        with opener.open(req, timeout=10) as r:
            body = r.read(2048)
            return "%s %d 字节 (%.1fs)" % (r.status, len(body), time.time() - t0)
    except Exception as e:
        return "HTTPS 请求失败: %r" % (e,)


def main():
    print("代理变量已清空，NO_PROXY=* —— 这一轮就是没有科学上网", flush=True)
    for label, host, port in TARGETS:
        ip, tcp, dt = probe(host, port)
        print("[%-10s] %-28s ip=%-16s %s (%.1fs)" % (label, host, ip or "-", tcp, dt), flush=True)
    print("", flush=True)
    for label, host, port in TARGETS[:3] + TARGETS[-1:]:
        print("[HTTPS] %-28s %s" % (host, http_probe(host)), flush=True)


if __name__ == "__main__":
    main()
