import json
import shutil
import sqlite3
from typing import Any
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


def _cfg_int(value: Any, default: int, lo: int, hi: int) -> int:
    """配置里的整数，非法就退回默认"""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _setting_int(value: Any, lo: int, hi: int, name: str) -> int:
    """设置页提交的整数，非法直接报错"""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        raise ValueError(f"{name}要填数字") from None
    if not (lo <= n <= hi):
        raise ValueError(f"{name}要在 {lo}~{hi} 之间")
    return n


def _setting_float(value: Any, lo: float, hi: float, name: str) -> float:
    """设置页提交的小数，非法直接报错"""
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name}要填数字") from None
    if not (lo <= n <= hi):
        raise ValueError(f"{name}要在 {lo}~{hi} 之间")
    return round(n, 2)


class _QuietHandler(SimpleHTTPRequestHandler):
    """去掉 http.server 的请求日志，免得刷屏"""
    def log_message(self, *args):
        pass

from jmcomic import JmMagicConstants, JmOption, JmcomicText

from backend.config import load_config, save_config

APP_DIR = Path.home() / ".jmreader"
# data/ 放再生不出来的用户数据，cache/ 放随时可删的缓存（受 cache.max_size_mb 约束）
DATA_DIR = APP_DIR / "data"
DATA_DB = DATA_DIR / "app.db"
CACHE_DIR = APP_DIR / "cache"
CACHE_DB = CACHE_DIR / "cache.db"
IMG_DIR = CACHE_DIR / "images"

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

# 搜索范围：五个 search_* 方法签名完全一致，只有 main_tag 不同，按名字分发就行
_SCOPE_MAP = {
    "site": "search_site",       # 站内（大杂烩）
    "work": "search_work",       # 作品名
    "author": "search_author",   # 作者
    "tag": "search_tag",         # 标签
    "actor": "search_actor",     # 登场角色
}

# 排序：前端只传语义名，jmcomic 的短码不透出去（图源改短码只动这里）
_ORDER_BY_MAP = {
    "latest": JmMagicConstants.ORDER_BY_LATEST,      # 最新
    "views": JmMagicConstants.ORDER_BY_VIEW,         # 观看
    "likes": JmMagicConstants.ORDER_BY_LIKE,         # 收藏
    "score": JmMagicConstants.ORDER_BY_SCORE,        # 评分
    "images": JmMagicConstants.ORDER_BY_PICTURE,     # 图片数
    "comments": JmMagicConstants.ORDER_BY_COMMENT,   # 评论数
}

class API:
    def __init__(self):
        # 缓存时长 / 下载并发数都来自 config.yaml（设置页可改，重启窗口后生效）
        cfg = load_config()
        self._dl_workers = _cfg_int(cfg["download"]["workers"], 8, 1, 32)
        self._photo_ttl = _cfg_int(cfg["cache"]["photo_ttl"], 86400, 0, 30 * 86400)
        self._max_cache_mb = _cfg_int(cfg["cache"]["max_size_mb"], 2048, 0, 102400)
        self._cleanup_interval = _cfg_int(cfg["cache"]["cleanup_interval"], 600, 30, 86400)
        self._album_ttl = _cfg_int(cfg["cache"]["album_ttl"], 86400, 0, 30 * 86400)
        self._search_ttl = _cfg_int(cfg["cache"]["search_ttl"], 3600, 0, 30 * 86400)
        self._ranking_ttl = _cfg_int(cfg["cache"]["ranking_ttl"], 3600, 0, 30 * 86400)
        self._comment_ttl = _cfg_int(cfg["cache"]["comment_ttl"], 600, 0, 30 * 86400)

        self.client = JmOption.default().new_jm_client()
        self._init_db()
        self.img_base = self._start_img_server()
        self._last_photo_id = ""   # 最近打开的章节，清理缓存时留着别删
        # 一个章节同时只允许一个下载批次：两批一起下会抢同一个 .part 文件
        # （这个锁只保护下面那个登记表，不串行化下载本身）
        self._dl_batch_lock = threading.Lock()
        self._dl_photo_ids: set[str] = set()
        threading.Thread(target=self._cache_loop, daemon=True).start()

    def _init_db(self) -> None:
        """建目录建库，并迁移老版本的单一 app.db"""
        for folder in (DATA_DIR, CACHE_DIR, IMG_DIR):
            folder.mkdir(parents=True, exist_ok=True)

        legacy_db = APP_DIR / "app.db"   # 老版本只有一个库，和缓存混在一起
        if legacy_db.exists() and not DATA_DB.exists():
            try:
                legacy_db.replace(DATA_DB)
            except OSError:
                shutil.copy2(legacy_db, DATA_DB)    # 搬不动就复制，别丢历史

        legacy_covers = CACHE_DIR / "covers"
        if legacy_covers.exists():
            shutil.rmtree(legacy_covers, ignore_errors=True)   # 旧版本下过封面，现在用远程图

        with sqlite3.connect(DATA_DB) as conn:
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
        with sqlite3.connect(CACHE_DB) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta_cache ("
                "key TEXT PRIMARY KEY, "
                "data_json TEXT NOT NULL, "
                "fetched_at REAL NOT NULL)"
            )
        self._move_legacy_cache()

    def _move_legacy_cache(self) -> None:
        """把老库里的 meta_cache 表搬进 cache.db，然后删掉"""
        with sqlite3.connect(DATA_DB) as conn:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_cache'"
            ).fetchone()
            if exists is None:
                return
            rows = conn.execute("SELECT key, data_json, fetched_at FROM meta_cache").fetchall()
            if rows:
                with sqlite3.connect(CACHE_DB) as cache_conn:
                    cache_conn.executemany(
                        "INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at)"
                        " VALUES (?, ?, ?)",
                        rows,
                    )
            conn.execute("DROP TABLE meta_cache")

    def _cache_get(self, key: str, ttl: float) -> list | None:
        """命中且未过期返回数据，否则返回 None"""
        with sqlite3.connect(CACHE_DB) as conn:
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
        with sqlite3.connect(CACHE_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at)"
                " VALUES (?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), time.time()),
            )

    def search(self, keyword: str, page: int = 1, scope: str = "site",
               order_by: str = "latest") -> list[dict[str, str]]:
        """
        搜索漫画，返回 [{"id", "title", "cover_url"}]

        scope 取 _SCOPE_MAP 的键（站内 / 作品名 / 作者 / 标签 / 角色），
        order_by 取 _ORDER_BY_MAP 的键；两者都进缓存键，换条件就是另一批结果
        """
        keyword = keyword.strip()
        if not keyword:
            return []
        if scope not in _SCOPE_MAP:
            raise ValueError(f"未知搜索范围: {scope}")
        if order_by not in _ORDER_BY_MAP:
            raise ValueError(f"未知排序: {order_by}")
        # 缓存键带上范围与排序：换个范围就是另一批结果，不能共用缓存
        key = f"search:{scope}:{order_by}:{keyword}:{page}"
        cached = self._cache_get(key, self._search_ttl)
        if cached is not None:
            return cached
        try:
            result_page = getattr(self.client, _SCOPE_MAP[scope])(
                search_query=keyword,
                page=page,
                order_by=_ORDER_BY_MAP[order_by],
            )
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

    def get_ranking(self, time_range: str, category: str = "all", page: int = 1,
                    order_by: str = "views") -> list[dict[str, str]]:
        """
        排行榜：time_range 取 "day"/"week"/"month"，
        category 取 "all"/"doujin"/"single"/"short"/"hanman"/"meiman"
        order_by 取 _ORDER_BY_MAP 的键（默认按观看，和以前一样）
        """
        if time_range not in _TIME_MAP:
            raise ValueError(f"未知榜单类型: {time_range}，应为 day/week/month")
        if category not in _CATEGORY_MAP:
            raise ValueError(f"未知分类: {category}")
        if order_by not in _ORDER_BY_MAP:
            raise ValueError(f"未知排序: {order_by}")
        key = f"ranking:{time_range}:{category}:{order_by}:{page}"
        cached = self._cache_get(key, self._ranking_ttl)
        if cached is not None:
            return cached
        try:
            result_page = self.client.categories_filter(
                page=page,
                time=_TIME_MAP[time_range],
                category=_CATEGORY_MAP[category],
                order_by=_ORDER_BY_MAP[order_by],
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
        """清缓存：接口元数据 + 章节图；data/ 里的用户数据不动"""
        with sqlite3.connect(CACHE_DB) as conn:
            n_rows = conn.execute("DELETE FROM meta_cache").rowcount
        n_files = 0
        for folder in IMG_DIR.glob("*"):
            for f in folder.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    f.unlink()
                    n_files += 1
                except OSError:
                    pass    # 正被图服务读着的文件删不掉，留给下次清理
        for folder in IMG_DIR.glob("*"):
            if folder.is_dir():
                try:
                    folder.rmdir()
                except OSError:
                    pass
        return {"meta_rows": n_rows, "cache_files": n_files}

    def _dir_size(self, path: Path) -> int:
        """目录里所有文件的总字节数"""
        total = 0
        for f in path.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass
        return total

    def get_cache_stats(self) -> dict:
        """缓存占用，设置页显示用"""
        return {
            "used_mb": round(self._dir_size(CACHE_DIR) / 1024 / 1024, 1),
            "limit_mb": self._max_cache_mb,
            "interval": self._cleanup_interval,
            "chapters": sum(1 for d in IMG_DIR.glob("*") if d.is_dir()),
        }

    def _keep_photo_ids(self) -> tuple[set[str], set[str]]:
        """返回 (绝对不删, 尽量别删)：正在下载/刚看的不删；最近读过的排在最后删"""
        with self._dl_batch_lock:      # 清理线程和下载线程会同时碰它
            always = set(self._dl_photo_ids)
        if self._last_photo_id:
            always.add(self._last_photo_id)
        with sqlite3.connect(DATA_DB) as conn:
            rows = conn.execute(
                "SELECT photo_id FROM history ORDER BY updated_at DESC LIMIT 3"
            ).fetchall()
        return always, {row[0] for row in rows} - always

    def cleanup_cache(self) -> dict:
        """把缓存压回上限：从最久没看过的章节开始整话删"""
        limit = self._max_cache_mb * 1024 * 1024
        # 过期到任何 TTL 之外的接口缓存一并清掉
        stale_before = time.time() - max(
            self._photo_ttl, self._album_ttl, self._search_ttl, self._ranking_ttl
        )
        with sqlite3.connect(CACHE_DB) as conn:
            conn.execute("DELETE FROM meta_cache WHERE fetched_at < ?", (stale_before,))

        used = self._dir_size(CACHE_DIR)
        result = {"used_mb": round(used / 1024 / 1024, 1), "removed_chapters": 0, "freed_mb": 0.0}
        if limit <= 0 or used <= limit:
            return result      # 0 = 不限

        always_keep, prefer_keep = self._keep_photo_ids()
        victims: list[tuple[bool, float, Path]] = []
        for folder in IMG_DIR.glob("*"):
            if not folder.is_dir() or folder.name in always_keep:
                continue
            mtimes = [f.stat().st_mtime for f in folder.glob("*") if f.is_file()]
            # 最近读过的排后面，其余按最久没碰过排前面
            victims.append((folder.name in prefer_keep, max(mtimes, default=0), folder))
        victims.sort(key=lambda item: (item[0], item[1]))

        freed = 0
        target = int(limit * 0.9)
        for _, _, folder in victims:
            if used - freed <= target:
                break
            for f in folder.glob("*"):
                if not f.is_file():
                    continue
                try:
                    size = f.stat().st_size    # 先量再删
                    f.unlink()
                    freed += size
                except OSError:
                    pass
            try:
                folder.rmdir()
            except OSError:
                pass
            result["removed_chapters"] += 1

        result["freed_mb"] = round(freed / 1024 / 1024, 1)
        result["used_mb"] = round((used - freed) / 1024 / 1024, 1)
        return result

    def _cache_loop(self) -> None:
        """定时整理缓存（守护线程）"""
        delay = min(self._cleanup_interval, 60)    # 启动后先看一次，别一开机就超限
        while True:
            time.sleep(delay)
            delay = self._cleanup_interval
            try:
                res = self.cleanup_cache()
                if res["removed_chapters"]:
                    print(f"[cache] 清理 {res['removed_chapters']} 话，释放 {res['freed_mb']} MB，"
                          f"现用 {res['used_mb']} MB")
            except Exception as e:      # 清理失败别把线程弄死
                print(f"[cache] 清理失败: {e}")

    def get_album_detail(self, album_id: str) -> dict:
        """
        漫画详情，返回 {"id", "title", "author", "authors", "description", "tags",
        "likes", "views", "comment_count", "pub_date", "update_date", "page_count",
        "cover_url", "related": [{"id", "title", "author", "cover_url"}],
        "chapters": [{"photo_id", "index", "title"}]}

        缓存里只放不随域名变的东西，封面地址（本子的和相关的）每次返回前现拼。
        """
        album_id = str(album_id).strip()
        # v2：老缓存没有发布日期 / 评论数 / 相关作品，加字段就换键，免得读到缺字段的旧数据
        key = f"album:v2:{album_id}"
        data = self._cache_get(key, self._album_ttl)
        if data is None:
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
                "comment_count": str(album.comment_count),
                "pub_date": album.pub_date,      # 发布日期
                "update_date": album.update_date,  # 更新日期，图源没给时是 "0"
                "page_count": album.page_count,
                "related": [
                    {
                        "id": str(rel["id"]),
                        "title": rel.get("name", ""),
                        "author": rel.get("author", ""),
                    }
                    for rel in (album.related_list or [])
                    if isinstance(rel, dict) and rel.get("id")
                ],
                "chapters": [
                    {"photo_id": str(pid), "index": str(pindex), "title": pname}
                    for pid, pindex, pname in album.episode_list
                ],
            }
            self._cache_set(key, data)
        # 封面地址现拼：图源域名会变（FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN），别把绝对地址写进缓存
        return {
            **data,
            "cover_url": JmcomicText.get_album_cover_url(album_id),
            "related": [
                {**rel, "cover_url": JmcomicText.get_album_cover_url(rel["id"])}
                for rel in data.get("related", [])
            ],
        }

    def get_comments(self, album_id: str, page: int = 1) -> dict:
        """
        本子评论（只读，不需要登录），返回 {"total", "has_more", "items": [
        {"nickname", "content", "created_at", "spoiler", "reply"}]}

        评论更新快，所以缓存时长单独用 cache.comment_ttl（默认 10 分钟）。
        """
        album_id = str(album_id).strip()
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            raise ValueError("评论页码要是数字") from None
        key = f"comments:{album_id}:{page}"
        cached = self._cache_get(key, self._comment_ttl)
        if cached is not None:
            return cached
        try:
            comment_page = self.client.album_pagination(album_id, page=page)
        except Exception as e:
            raise RuntimeError(f"评论获取失败: {e}") from e
        items = [
            {
                "nickname": cm.nickname or cm.username or "匿名",
                "content": cm.content or "",
                "created_at": cm.created_at or "",
                "spoiler": bool(cm.is_spoiler),
                "reply": cm.parent_comment_id is not None,
            }
            for cm in comment_page
        ]
        data = {
            "total": int(comment_page.total or 0),
            # 满一页就当还有下一页，前端靠它决定"看更多"要不要留着
            "has_more": len(items) >= comment_page.page_size,
            "items": items,
        }
        self._cache_set(key, data)
        return data

    def _start_img_server(self) -> str:
        """启动本地图片静态服务（只监听本机），返回 base url"""
        handler = partial(_QuietHandler, directory=str(CACHE_DIR))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)  # 端口 0 = 系统自动分配
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{port}"

    def get_chapter(self, photo_id: str) -> dict:
        """
        返回 {"photo_id", "images"}。
        只缓存文件名列表，URL 每次用当前 img_base 拼（图服务端口每次启动都变）。
        """
        photo_id = str(photo_id).strip()
        self._last_photo_id = photo_id    # 正在看的这一话缓存里留着
        img_dir = IMG_DIR / photo_id
        img_dir.mkdir(parents=True, exist_ok=True)

        key = f"photo:{photo_id}"
        files: list[str] | None = self._cache_get(key, self._photo_ttl)

        if files is None:
            try:
                photo = self.client.get_photo_detail(photo_id)
            except Exception as e:
                raise RuntimeError(f"章节获取失败: {e}") from e
            files = [img.filename for img in photo]
            self._cache_set(key, files)
            missing = [
                (img, img_dir / img.filename)
                for img in photo
                if not (img_dir / img.filename).exists()
            ]
            if missing:
                self._spawn_download(photo_id, missing)
        elif any(not (img_dir / name).exists() for name in files):
            # 列表命中缓存、图还没下全：把取详情那次网络请求也挪到后台，别拖慢这次返回
            self._spawn_download(photo_id, None)

        return {
            "photo_id": photo_id,
            "images": [f"{self.img_base}/images/{photo_id}/{name}" for name in files],
        }

    def _spawn_download(self, photo_id: str, jobs: list[tuple] | None) -> None:
        """起一个后台下载批次；jobs 为 None 表示要去网络取图列表（同一章节只跑一批）"""
        with self._dl_batch_lock:
            if photo_id in self._dl_photo_ids:
                return
            self._dl_photo_ids.add(photo_id)
        threading.Thread(target=self._run_download, args=(photo_id, jobs), daemon=True).start()

    def _run_download(self, photo_id: str, jobs: list[tuple] | None) -> None:
        try:
            if jobs is None:
                img_dir = IMG_DIR / photo_id
                try:
                    photo = self.client.get_photo_detail(photo_id)
                except Exception:
                    return  # 网络不通就留着下次进章节再补
                jobs = [
                    (img, img_dir / img.filename)
                    for img in photo
                    if not (img_dir / img.filename).exists()
                ]
            self._download_images(jobs)
        finally:
            with self._dl_batch_lock:
                self._dl_photo_ids.discard(photo_id)

    def _download_images(self, jobs: list[tuple]) -> None:
        """并发下载；每张图先写 .part 再改名，中断不留坏文件"""
        jobs = [(img, path) for img, path in jobs if not path.exists()]
        if not jobs:
            return
        with ThreadPoolExecutor(max_workers=self._dl_workers) as pool:
            list(pool.map(self._download_one, jobs))

    def _download_one(self, job: tuple) -> None:
        img, path = job
        if path.exists():
            return
        # 临时名要保留真实后缀：jmcomic 按输出后缀定编码，用 .part 当后缀会直接抛错
        tmp = path.with_name(f"{path.stem}.part{path.suffix}")
        try:
            self.client.download_by_image_detail(img, str(tmp))
            tmp.rename(path)
        except Exception:
            tmp.unlink(missing_ok=True)

    def save_progress(self, album_id: str, photo_id: str, page_index: int,
                    title: str = "", cover_url: str = "") -> None:
        """保存阅读进度；title/cover_url 给首页"继续阅读"列表展示用"""
        with sqlite3.connect(DATA_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO history"
                " (album_id, photo_id, page_index, title, cover_url, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (str(album_id), str(photo_id), int(page_index),
                title, cover_url, time.time()),
            )

    def get_progress(self, album_id: str, photo_id: str) -> int:
        """返回上次看到的页码（从 0 开始），没有记录返回 0"""
        with sqlite3.connect(DATA_DB) as conn:
            row = conn.execute(
                "SELECT page_index FROM history WHERE album_id=? AND photo_id=?",
                (str(album_id), str(photo_id)),
            ).fetchone()
        return int(row[0]) if row else 0

    def get_history(self, limit: int = 10) -> list[dict]:
        """最近阅读：一部漫画一条，取最近读的那一话，按更新时间倒序"""
        with sqlite3.connect(DATA_DB) as conn:
            rows = conn.execute(
                "SELECT album_id, photo_id, page_index, title, cover_url, updated_at FROM ("
                " SELECT *, ROW_NUMBER() OVER (PARTITION BY album_id ORDER BY updated_at DESC) AS rn"
                " FROM history) WHERE rn = 1 ORDER BY updated_at DESC LIMIT ?",
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

    def get_album_progress(self, album_id: str) -> dict | None:
        """这部漫画最近读到哪一话的哪一页；没读过返回 None"""
        with sqlite3.connect(DATA_DB) as conn:
            row = conn.execute(
                "SELECT photo_id, page_index, title FROM history"
                " WHERE album_id = ? ORDER BY updated_at DESC LIMIT 1",
                (str(album_id),),
            ).fetchone()
        if row is None:
            return None
        return {"photo_id": row[0], "page_index": int(row[1]), "title": row[2]}

    def get_settings(self) -> dict:
        """当前配置（含默认值）"""
        return load_config()

    def save_settings(self, settings: dict) -> dict:
        """保存设置到 config.yaml 并返回完整配置（重启生效的项由前端提示）"""
        if not isinstance(settings, dict):
            raise RuntimeError("保存失败：设置内容格式不对")
        cfg = load_config()
        try:
            win = settings.get("window") or {}
            if "title" in win:
                title = str(win["title"]).strip()
                if not title:
                    raise ValueError("窗口标题不能为空")
                cfg["window"]["title"] = title
            if "width" in win:
                cfg["window"]["width"] = _setting_int(win["width"], 400, 5000, "窗口宽度")
            if "height" in win:
                cfg["window"]["height"] = _setting_int(win["height"], 400, 5000, "窗口高度")
            if "min_size" in win:
                size = win["min_size"]
                if not isinstance(size, (list, tuple)) or len(size) != 2:
                    raise ValueError("最小尺寸要填两个数字（宽、高）")
                cfg["window"]["min_size"] = [
                    _setting_int(size[0], 200, 5000, "最小宽度"),
                    _setting_int(size[1], 200, 5000, "最小高度"),
                ]
            if "glass" in win:
                glass_kind = str(win["glass"]).strip().lower()
                if glass_kind not in ("none", "mica", "acrylic", "tabbed"):
                    raise ValueError("窗口毛玻璃只能是 none / mica / acrylic / tabbed")
                cfg["window"]["glass"] = glass_kind
            if "glass_opacity" in win:
                cfg["window"]["glass_opacity"] = _setting_float(
                    win["glass_opacity"], 0.35, 1.0, "窗口不透明度")

            dev = settings.get("dev") or {}
            if "url" in dev:
                url = str(dev["url"]).strip()
                if not url.startswith(("http://", "https://", "file://")):
                    raise ValueError("启动地址要以 http:// 或 https:// 或 file:// 开头")
                cfg["dev"]["url"] = url
            if "debug" in dev:
                cfg["dev"]["debug"] = bool(dev["debug"])

            reader = settings.get("reader") or {}
            for key in ("restore_progress", "click_to_page"):
                if key in reader:
                    cfg["reader"][key] = bool(reader[key])
            if "mode" in reader:
                if reader["mode"] not in ("webtoon", "single"):
                    raise ValueError("阅读模式只能是 webtoon（连续滚动）或 single（单页翻页）")
                cfg["reader"]["mode"] = reader["mode"]
            if "background" in reader:
                if reader["background"] not in ("dark", "black", "gray", "light"):
                    raise ValueError("背景色只能是 dark / black / gray / light")
                cfg["reader"]["background"] = reader["background"]
            if "page_gap" in reader:
                cfg["reader"]["page_gap"] = _setting_int(reader["page_gap"], 0, 64, "页间距")
            if "width" in reader:
                cfg["reader"]["width"] = _setting_int(reader["width"], 0, 2400, "阅读器图片宽度")
            if "auto_scroll" in reader:
                cfg["reader"]["auto_scroll"] = _setting_int(reader["auto_scroll"], 0, 1000, "自动滚屏速度")

            detail = settings.get("detail") or {}
            if "chapters_collapse" in detail:
                cfg["detail"]["chapters_collapse"] = _setting_int(
                    detail["chapters_collapse"], 0, 500, "章节折叠阈值")
            if "comment_preview" in detail:
                cfg["detail"]["comment_preview"] = _setting_int(
                    detail["comment_preview"], 0, 50, "评论预览条数")

            download = settings.get("download") or {}
            if "workers" in download:
                cfg["download"]["workers"] = _setting_int(download["workers"], 1, 32, "下载并发数")

            cache = settings.get("cache") or {}
            for key, label, lo, hi in (
                ("photo_ttl", "章节图列表缓存时长", 0, 30 * 86400),
                ("album_ttl", "漫画详情缓存时长", 0, 30 * 86400),
                ("search_ttl", "搜索缓存时长", 0, 30 * 86400),
                ("ranking_ttl", "榜单缓存时长", 0, 30 * 86400),
                ("comment_ttl", "评论缓存时长", 0, 30 * 86400),
                ("max_size_mb", "缓存上限", 0, 102400),
                ("cleanup_interval", "定时清理间隔", 30, 86400),
            ):
                if key in cache:
                    cfg["cache"][key] = _setting_int(cache[key], lo, hi, label)
        except ValueError as e:
            raise RuntimeError(f"保存失败：{e}") from e

        save_config(cfg)
        return cfg
