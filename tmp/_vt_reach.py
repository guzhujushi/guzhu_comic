import os, time, urllib.request, urllib.error

HASH = "724a5bff6f8ac27e98dd41b9612b52b1d42f0127100833df54c601cc2fdb2ec45"
URL = "https://www.virustotal.com/api/v3/files/" + HASH

def try_get(label, proxy):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({} if proxy is None else {"https": proxy, "http": proxy}))
    req = urllib.request.Request(URL, headers={"x-apikey": "dummy"})
    t0 = time.time()
    try:
        with opener.open(req, timeout=12) as r:
            return "%s -> %s (%.1fs)" % (label, r.status, time.time() - t0)
    except urllib.error.HTTPError as e:
        return "%s -> HTTP %s（能连上服务，只是 key 不对）(%.1fs)" % (label, e.code, time.time() - t0)
    except Exception as e:
        return "%s -> 连不上：%r (%.1fs)" % (label, str(e)[:70], time.time() - t0)

print(try_get("直连  ", None), flush=True)
print(try_get("走7890", "http://127.0.0.1:7890"), flush=True)
