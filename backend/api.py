import json
import sqlite3
import time
from pathlib import Path

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
class API:
    def __init__(self):
        self.client = JmOption.default().new_jm_client()
        APP_DIR.mkdir(parents=True, exist_ok=True)
        COVER_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta_cache ("
                "key TEXT PRIMARY KEY, "
                "data_json TEXT NOT NULL, "
                "fetched_at REAL NOT NULL)"
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
        搜索本子，返回 [{"id", "title", "cover_url"}]，结果缓存 1 小时
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

    def get_ranking(self, time_range: str, page: int = 1) -> list[dict[str, str]]:
        """
        排行榜：time_range 取 "day" / "week" / "month"
        返回 [{"id", "title", "cover"}]，cover 为本地路径
        """
        if time_range not in _TIME_MAP:
            raise ValueError(f"未知榜单类型: {time_range}，应为 day/week/month")
        key = f"ranking:{time_range}:{page}"
        cached = self._cache_get(key, RANKING_TTL)
        if cached is not None:
            return cached
        try:
            result_page = self.client.categories_filter(
                page=page,
                time=_TIME_MAP[time_range],
                category=JmMagicConstants.CATEGORY_ALL,
                order_by=JmMagicConstants.ORDER_BY_VIEW,
            )
        except Exception as e:
            raise RuntimeError(f"榜单获取失败: {e}") from e
        data = [
            {
                "id": str(album_id),
                "title": title,
                "cover": self._cover_path(str(album_id)),
            }
            for album_id, title in result_page
        ]
        self._cache_set(key, data)
        return data
