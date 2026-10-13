import json
import sqlite3
import time
from pathlib import Path
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class _QuietHandler(SimpleHTTPRequestHandler):
    """去掉 http.server 的请求日志，免得刷屏"""
    def log_message(self, *args):
        pass

from jmcomic import JmMagicConstants, JmOption, JmcomicText

APP_DIR = Path.home() / ".jmreader"
COVER_DIR = APP_DIR / "cache" / "covers"
DB_PATH = APP_DIR / "app.db"

RANKING_TTL = 3600  # 排行榜缓存 1 小时
SEARCH_TTL = 3600  

# 前端传 "day"/"week"/"month"，这里映射到 jmcomic 常量
_TIME_MAP = {
    "day": JmMagicConstants.TIME_TODAY,
    "week": JmMagicConstants.TIME_WEEK,
    "month": JmMagicConstants.TIME_MONTH,
}

_CATEGORY_MAP = {
    "all": JmMagicConstants.CATEGORY_ALL,       # 全部
    "doujin": JmMagicConstants.CATEGORY_DOUJIN,  # 同人
    "single": JmMagicConstants.CATEGORY_SINGLE,  # 单本
    "short": JmMagicConstants.CATEGORY_SHORT,    # 短篇
    "hanman": JmMagicConstants.CATEGORY_HANMAN,  # 韩漫
    "meiman": JmMagicConstants.CATEGORY_MEIMAN,  # 美漫
}

class API:
    def __init__(self):
        self.client = JmOption.default().new_jm_client()
        APP_DIR.mkdir(parents=True, exist_ok=True)
        COVER_DIR.mkdir(parents=True, exist_ok=True)
        (APP_DIR / "cache" / "images").mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.img_base = self._start_img_server()

    def _init_db(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta_cache ("
                "key TEXT PRIMARY KEY, "
                "data_json TEXT NOT NULL, "
                "fetched_at REAL NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS history ("
                "album_id TEXT NOT NULL, "
                "photo_id TEXT NOT NULL, "
                "page_index INTEGER NOT NULL DEFAULT 0, "
                "title TEXT NOT NULL DEFAULT '', "
                "cover_url TEXT NOT NULL DEFAULT '', "
                "updated_at REAL NOT NULL, "
                "PRIMARY KEY (album_id, photo_id))"
            )

    def _cache_get(self, key: str, ttl: float) -> list | None:
        """命中且未过期返回数据，否则返回 None"""
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT data_json, fetched_at FROM meta_cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        data_json, fetched_at = row
        if time.time() - fetched_at > ttl:
            return None
        return json.loads(data_json)

    def _cache_set(self, key: str, data: list) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at)"
                " VALUES (?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), time.time()),
            )

    def _cover_path(self, album_id: str) -> str:
        """返回封面本地路径；不存在则下载"""
        path = COVER_DIR / f"{album_id}.jpg"
        if not path.exists():
            try:
                self.client.download_album_cover(album_id, str(path))
            except Exception:
                return ""  # 单张封面失败不拖累整个列表，前端用占位图
        return str(path)

    def search(self, keyword: str, page: int = 1) -> list[dict[str, str]]:
        """
        搜索漫画，返回 [{"id", "title", "cover_url"}]，结果缓存 1 小时
        """
        keyword = keyword.strip()
        if not keyword:
            return []
        key = f"search:{keyword}:{page}"
        cached = self._cache_get(key, SEARCH_TTL)
        if cached is not None:
            return cached
        try:
            result_page = self.client.search_site(search_query=keyword, page=page)
        except Exception as e:
            raise RuntimeError(f"搜索失败: {e}") from e
        data = [
            {
                "id": str(album_id),
                "title": title,
                "cover_url": JmcomicText.get_album_cover_url(str(album_id)),
            }
        for album_id, title in result_page
        ]
        self._cache_set(key, data)
        return data

    def get_ranking(self, time_range: str, category: str = "all", page: int = 1) -> list[dict[str, str]]:
        """
        排行榜：time_range 取 "day"/"week"/"month"，
        category 取 "all"/"doujin"/"single"/"short"/"hanman"/"meiman"
        """
        if time_range not in _TIME_MAP:
            raise ValueError(f"未知榜单类型: {time_range}，应为 day/week/month")
        if category not in _CATEGORY_MAP:
            raise ValueError(f"未知分类: {category}")
        key = f"ranking:{time_range}:{category}:{page}"
        cached = self._cache_get(key, RANKING_TTL)
        if cached is not None:
            return cached
        try:
            result_page = self.client.categories_filter(
                page=page,
                time=_TIME_MAP[time_range],
                category=_CATEGORY_MAP[category],
                order_by=JmMagicConstants.ORDER_BY_VIEW,
            )
        except Exception as e:
            raise RuntimeError(f"榜单获取失败: {e}") from e
        data = [
            {
                "id": str(album_id),
                "title": title,
                "cover_url": JmcomicText.get_album_cover_url(str(album_id)),
            }
            for album_id, title in result_page
        ]
        self._cache_set(key, data)
        return data
    
    def clear_cache(self) -> dict[str, int]:
        """
        清缓存：删 meta_cache 全表 + covers 目录下的文件
        """
        with sqlite3.connect(DB_PATH) as conn:
            n_rows = conn.execute("DELETE FROM meta_cache").rowcount
        n_files = 0
        for f in COVER_DIR.glob("*"):
            if f.is_file():
                f.unlink()
                n_files += 1
        return {"meta_rows": n_rows, "cover_files": n_files}

    ALBUM_TTL = 86400

    def get_album_detail(self, album_id: str) -> dict:
        """
        漫画详情，返回 {"id", "title", "author", "authors", "description",
        "tags", "likes", "views", "page_count", "cover_url",
        "chapters": [{"photo_id", "index", "title"}]}
        """
        album_id = str(album_id).strip()
        key = f"album:{album_id}"
        cached = self._cache_get(key, self.ALBUM_TTL)
        if cached is not None:
            return cached
        try:
            album = self.client.get_album_detail(album_id)
        except Exception as e:
            raise RuntimeError(f"详情获取失败: {e}") from e
        data = {
            "id": str(album.album_id),
            "title": album.name,
            "author": album.author,          # 第一作者
            "authors": list(album.authors),  # 全部作者
            "description": album.description,
            "tags": list(album.tags),
            "likes": str(album.likes),
            "views": str(album.views),
            "page_count": album.page_count,
            "cover_url": JmcomicText.get_album_cover_url(album_id),
            "chapters": [
                {"photo_id": str(pid), "index": str(pindex), "title": pname}
                for pid, pindex, pname in album.episode_list
            ],
        }
        self._cache_set(key, data)
        return data

    def _start_img_server(self) -> str:
        """启动本地图片静态服务（只监听本机），返回 base url"""
        handler = partial(_QuietHandler, directory=str(APP_DIR / "cache"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)  # 端口 0 = 系统自动分配
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{port}"

    def get_chapter(self, photo_id: str) -> dict:
        """
        章节图片：下载（解密）到本地，返回 {"photo_id", "images": [本地 http url]}
        已下载过的直接复用，不重复请求
        """
        photo_id = str(photo_id).strip()
        img_dir = APP_DIR / "cache" / "images" / photo_id
        img_dir.mkdir(parents=True, exist_ok=True)
        try:
            photo = self.client.get_photo_detail(photo_id)
        except Exception as e:
            raise RuntimeError(f"章节获取失败: {e}") from e
        urls = []
        for img in photo:  # 迭代产生 JmImageDetail
            path = img_dir / img.filename
            if not path.exists():
                try:
                    self.client.download_by_image_detail(img, str(path))
                except Exception as e:
                    raise RuntimeError(f"图片下载失败 {img.filename}: {e}") from e
            urls.append(f"{self.img_base}/images/{photo_id}/{img.filename}")
        return {"photo_id": photo_id, "images": urls}

    def save_progress(self, album_id: str, photo_id: str, page_index: int,
                    title: str = "", cover_url: str = "") -> None:
        """保存阅读进度；title/cover_url 给首页"继续阅读"列表展示用"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO history"
                " (album_id, photo_id, page_index, title, cover_url, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (str(album_id), str(photo_id), int(page_index),
                title, cover_url, time.time()),
            )

    def get_progress(self, album_id: str, photo_id: str) -> int:
        """返回上次看到的页码（从 0 开始），没有记录返回 0"""
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT page_index FROM history WHERE album_id=? AND photo_id=?",
                (str(album_id), str(photo_id)),
            ).fetchone()
        return int(row[0]) if row else 0

    def get_history(self, limit: int = 10) -> list[dict]:
        """最近阅读，按更新时间倒序"""
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT album_id, photo_id, page_index, title, cover_url, updated_at"
                " FROM history ORDER BY updated_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            {
                "album_id": r[0],
                "photo_id": r[1],
                "page_index": r[2],
                "title": r[3],
                "cover_url": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]