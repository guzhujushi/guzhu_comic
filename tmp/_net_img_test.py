# -*- coding: utf-8 -*-
r"""直连（无代理）取图诊断：到底是哪一步、哪个域名不通。"""
import os
import socket
import time
from urllib.parse import urlparse

for k in list(os.environ):
    if k.lower() in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy"):
        del os.environ[k]
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from curl_cffi import requests as cc
from jmcomic import JmOption

client = JmOption.default().new_jm_client()
t0 = time.time()
photo = client.get_photo_detail("209828")
print("详情 OK：%s 共 %d 张（%.1fs）" % (photo.photo_id, len(photo), time.time() - t0), flush=True)

urls = []
for img in list(photo)[:3]:
    u = getattr(img, "download_url", None) or getattr(img, "img_url", None)
    urls.append(u)
for u in urls:
    print("  URL: " + str(u)[:110], flush=True)

hosts = sorted({urlparse(u).hostname for u in urls if u})
for h in hosts:
    try:
        ip = socket.gethostbyname(h)
    except Exception as e:
        print("  [DNS] %-32s 失败 %r" % (h, e), flush=True)
        continue
    t1 = time.time()
    try:
        with socket.create_connection((ip, 443), timeout=6):
            print("  [TCP] %-32s %s 通 (%.1fs)" % (h, ip, time.time() - t1), flush=True)
    except Exception as e:
        print("  [TCP] %-32s %s 连不上 %r" % (h, ip, e), flush=True)

for u in urls:
    t2 = time.time()
    try:
        r = cc.get(u, impersonate="chrome", timeout=12)
        print("  [GET] %s -> %s %s %d 字节 (%.1fs)"
              % (urlparse(u).hostname, r.status_code, r.headers.get("content-type"), len(r.content), time.time() - t2), flush=True)
    except Exception as e:
        print("  [GET] %s -> 失败 %r (%.1fs)" % (urlparse(u).hostname, str(e)[:80], time.time() - t2), flush=True)
