# -*- coding: utf-8 -*-
r"""把这一轮改到的后端读接口在**真库**上各跑一遍：只读，不写、不联网取数据。"""
import json
import sys

sys.path.insert(0, r"D:\guzhu_comic")
from backend.api import API   # noqa: E402

api = API()
out = {}
out["get_settings"] = sorted(api.get_settings().keys())
out["get_history"] = len(api.get_history(60))
out["get_downloads"] = len(api.get_downloads())
out["get_favorites"] = len(api.get_favorites(200))
out["get_search_log"] = len(api.get_search_log(12))
out["get_cache_stats"] = api.get_cache_stats()
out["get_taste_profile"] = {"tags": len(api.get_taste_profile()["tags"]),
                            "authors": len(api.get_taste_profile()["authors"])}
out["get_album_progress"] = api.get_album_progress("209827")
print("SMOKE " + json.dumps(out, ensure_ascii=False))