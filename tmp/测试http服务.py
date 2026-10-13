import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api import API

api = API()
r = api.get_chapter("123456")
print("共", len(r["images"]), "张")
print(r["images"][0])
input("把 URL 粘到浏览器验证，确认后按回车退出...")
