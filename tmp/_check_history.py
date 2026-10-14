# -*- coding: utf-8 -*-
"""核一下前端「继续阅读」依赖的那条接口：真 API 实例上 get_history(1) 返回什么。"""
import sys, json
sys.path.insert(0, r"D:\guzhu_comic")
from backend.api import API
api = API()
rows = api.get_history(1)
print("rows =", json.dumps(rows, ensure_ascii=False)[:400])
if rows:
    r = rows[0]
    need = ["album_id", "photo_id", "page_index", "title", "cover_url", "updated_at"]
    print("缺字段 =", [k for k in need if k not in r])
    print("types  =", {k: type(r[k]).__name__ for k in need})