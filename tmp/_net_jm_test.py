# -*- coding: utf-8 -*-
r"""用**应用自己的客户端**做 A/B：直连 vs 走 7890 代理，看能不能真拿到数据。

跑法：.venv/Scripts/python.exe tmp/_net_jm_test.py direct
      .venv/Scripts/python.exe tmp/_net_jm_test.py proxy
"""
import os
import sys
import time

MODE = (sys.argv[1] if len(sys.argv) > 1 else "direct").lower()
if MODE == "direct":
    for k in list(os.environ):
        if k.lower() in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy"):
            del os.environ[k]
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
else:
    os.environ["HTTP_PROXY"] = os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
    os.environ["http_proxy"] = os.environ["https_proxy"] = "http://127.0.0.1:7890"

print("=== 模式：%s ===" % MODE, flush=True)

# 1) 先看 curl_cffi 直接打各 API 域名（这才是应用真正的请求姿势）
try:
    from curl_cffi import requests as cc
    from jmcomic import JmModuleConfig as M

    for dom in M.DOMAIN_API_LIST[:4]:
        t0 = time.time()
        try:
            r = cc.get("https://%s/" % dom, impersonate="chrome", timeout=8)
            print("  curl_cffi https://%-20s -> %s (%d 字节, %.1fs)"
                  % (dom, r.status_code, len(r.content), time.time() - t0), flush=True)
        except Exception as e:
            print("  curl_cffi https://%-20s -> 失败 %r (%.1fs)"
                  % (dom, str(e)[:90], time.time() - t0), flush=True)
except Exception as e:
    print("  curl_cffi 不可用：%r" % (e,), flush=True)

# 2) 再用 jmcomic 自己的客户端取一份真数据（跟应用里那条路一样）
print("  --- jmcomic 取详情（发布页/重定向那步会超时也没关系）---", flush=True)
t0 = time.time()
try:
    from jmcomic import JmOption
    opt = JmOption.default()
    client = opt.new_jm_client()
    album = client.get_album_detail("422866")
    print("  成功：album=%s 章节数=%d (%.1fs)"
          % (getattr(album, "album_id", "?"), len(album), time.time() - t0), flush=True)
except Exception as e:
    print("  失败：%r (%.1fs)" % (str(e)[:300], time.time() - t0), flush=True)
