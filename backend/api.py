import json
import shutil
import sqlite3
from typing import Any
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from functools import partial
from http.server import ThreadingHTTPServer


def _cfg_int(value: Any, default: int, lo: int, hi: int) -> int:
    """配置里的整数，非法就退回默认"""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _cfg_float(value: Any, default: float, lo: float, hi: float) -> float:
    """配置里的小数，非法就退回默认"""
    try:
        n = float(value)
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


def _setting_section(settings: dict, name: str, label: str) -> dict:
    """
    取设置里的一段。没给就是空（这次保存不动它）；给了但不是映射（手改过 / 老前端发来的
    `window: 5`）当场报错说清楚 —— 不拦的话下面那句 `"title" in win` 会抛 TypeError 直穿到 JS 桥。
    """
    value = settings.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label}那一段要是一个小节（键值对）")
    return value


# 写冲突时等多久（秒）：整本下载逐话写库、界面同时存进度，默认的 5 秒偶尔不够
DB_TIMEOUT = 15.0

# 文件名里不许出现的字符（Windows 的路径分隔符、通配符、控制字符）
_BAD_NAME_CHARS = frozenset('<>:"|?*' + "".join(chr(c) for c in range(32)))


def _img_name(img: Any) -> str:
    """
    图源给的图片文件名 → 只取"纯文件名"，一个路径分隔符都不许留。

    `img.filename` 是 jmcomic 从**图源页面里那个字符串**切出来的（`data_original[x+1:y]` 加上后缀），
    也就是远端说了算。而下游是 `目录 / name` 这么拼的 —— 名字里只要有 `\\` 或 `..`，那就成了
    "图源（或它经过的 CDN）被投毒就能往下载 / 缓存目录外面写文件"。所以这一层必须自己收口：

      * 只认最后一段（`a/b/00001.webp` → `00001.webp`），分隔符与 `..` 一律进不来；
      * 后缀尽量保住（jmcomic 按后缀决定解码方式，`.gif` 那条路跟别的图不一样）；
      * 名字实在不能用（空 / `.` / `..` / 带非法字符）就按序号命名 —— 图源正常给的本就是
        `00001.webp` 这种，退回序号只是换个名字，图画本身不受影响。
    """
    raw = str(getattr(img, "filename", "") or "")
    tail = raw.replace("\\", "/").split("/")[-1]
    # 末尾的点和空格在 Windows 上会被偷偷吃掉（"... " 会变成空名），所以也算不可用
    if tail and tail not in (".", "..") and tail == tail.rstrip(" .") \
            and not (set(tail) & _BAD_NAME_CHARS):
        return tail
    # 非法字符先剔掉再看后缀：本来叫 x.webp\x00 的，还能认出是 .webp（解码方式跟后缀走）
    clean = "".join(ch for ch in tail if ch not in _BAD_NAME_CHARS).rstrip(" .")
    suffix = Path(clean).suffix
    if not suffix or "/" in suffix or "\\" in suffix:
        suffix = ".jpg"
    return f"{int(getattr(img, 'index', 0) or 0):05d}{suffix}"


def _db(path: Path) -> sqlite3.Connection:
    """
    开一个 sqlite 连接。

    `with sqlite3.connect(...)` 有个坑：`with` 只提交 / 回滚，**不关连接** —— 句柄要等这个
    函数返回、局部名被回收才还回去。所以统一走这里，顺手把等锁的上限从默认 5 秒放到 15 秒。
    """
    return sqlite3.connect(path, timeout=DB_TIMEOUT)

from jmcomic import JmMagicConstants, JmOption, JmcomicText

from backend.config import load_config, save_config
from backend.paths import (APP_DIR, CACHE_DIR, CACHE_DB, DATA_DB, DATA_DIR, IMG_DIR,
                           resolve_download_dir)
# 本地静态服务的基类：图服务与打包后的前端页面共用（打包态是同一个端口）
from backend.server import _QuietHandler   # noqa: F401

# 用户目录（~/.jmreader）与只读资源目录都从 backend.paths 来 —— 那里是源码态 / 冻结态的
# 唯一分叉点。import 进来保持旧名字，api.py 里的用法一行不用改。

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
    def __init__(self, base_url: str | None = None):
        """
        base_url 给了就用它当图片的 base（打包态：main.py 起的静态服务跟页面同一个端口）；
        不给就自己起一个（源码态，端口由系统随机分配）。
        """
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
        # 预加载（列表 -> 详情缓存、详情/阅读 -> 章节图）：见 config.yaml 的 prefetch 组
        self._pf_albums = _cfg_int(cfg["prefetch"]["albums"], 12, 0, 30)
        self._pf_images = _cfg_int(cfg["prefetch"]["chapter_images"], 3, 0, 20)
        # 推荐（热度候选池 + 收藏 / 搜索画像）：见 config.yaml 的 recommend 组
        self._rc_limit = _cfg_int(cfg["recommend"]["limit"], 10, 0, 50)
        self._rc_candidates = _cfg_int(cfg["recommend"]["candidates"], 40, 5, 200)
        self._rc_hot = _cfg_float(cfg["recommend"]["hot_weight"], 0.3, 0.0, 1.0)
        self._rc_author_boost = _cfg_float(cfg["recommend"]["author_boost"], 1.5, 0.0, 5.0)
        self._rc_half_life = _cfg_int(cfg["recommend"]["half_life_days"], 30, 1, 365)
        # 整本离线下载（见 config.yaml 的 download 组）：目录、重试、开窗续传
        self._dl_retries = _cfg_int(cfg["download"]["retries"], 3, 0, 10)
        self._dl_auto_resume = bool(cfg["download"]["auto_resume"])
        # 名字带下划线是有意的：pywebview 会把 js_api 的公开属性递归展开成 JS 方法
        # （Path 能展开出 300 多个），见下面 `_jm` 那段注释
        self._download_dir = resolve_download_dir(cfg["download"]["dir"])

        # jmcomic 建客户端时要连图源（更新域名、拉 setting），图源抖一下这一步就能卡十几秒。
        # 所以挪到"第一次真要数据"的时候再做（见下面的 `_jm`），窗口立刻就能起来，
        # 页面上先看骨架，别让人对着一个还没出现的窗口发呆。
        self._client_lock = threading.Lock()
        self._client = None
        self._init_db()
        self.img_base = base_url or self._start_img_server()
        self._last_photo_id = ""   # 最近打开的章节，清理缓存时留着别删
        # 一个章节同时只允许一个下载批次：两批一起下会抢同一个 .part 文件
        # （这个锁只保护下面那个登记表，不串行化下载本身）
        self._dl_batch_lock = threading.Lock()
        self._dl_photo_ids: set[str] = set()
        # 批次在跑的时候又有人要整话（用户真进了阅读器）：记一笔，等这批跑完补一次
        self._dl_pending: set[str] = set()
        # 同一把钥匙同一时刻只让一个线程去图源取（见 _fetch_guard）：闪屏预热和页面自己发的
        # 请求经常前后脚撞上，不认一下的话图源那边同一份数据要拉两遍
        self._inflight: dict[str, threading.Event] = {}
        self._inflight_lock = threading.Lock()
        self._inflight_wait = 30.0   # 等别人取的上限（秒）；等不到就自己取，别干等
        # 这次开窗期间已经预热过详情的本子（重复调用直接跳过，别白读一次库）
        self._prefetch_done: set[str] = set()
        # 整本下载：一本一个线程，逐话串行。断点续传不靠内存里的计数 ——
        # 磁盘上落地的文件就是进度，续传时把缺的挑出来补。
        self._album_dl_lock = threading.Lock()
        self._album_dl_threads: dict[str, threading.Thread] = {}
        self._album_dl_pause: dict[str, threading.Event] = {}   # set = 暂停
        self._album_dl_stop: dict[str, threading.Event] = {}    # set = 任务已删，别再写库
        # 开窗的同时后台先把图源连上（更新域名、拉 setting 那一步可能要十几秒），
        # 这样窗口立刻就能出来，首页第一次要数据时也不用干等
        threading.Thread(target=self._warm_client, daemon=True).start()
        threading.Thread(target=self._cache_loop, daemon=True).start()
        if self._dl_auto_resume:
            threading.Thread(target=self._resume_downloads_loop, daemon=True).start()

    @property
    def _jm(self):
        """jmcomic 客户端：第一次用到时才建（连图源那一步别挡着开窗）。

        **名字必须带下划线**：pywebview 注入 JS 桥时会 `dir(js_api)` + `getattr` 把每个属性
        递归展开成 `window.pywebview.api.*`（`webview/util.py` 的 `get_functions`，它只跳过
        下划线开头的名字）。这个属性一旦叫 `client`，就会 ① 在注入线程里当场把客户端建出来
        （连图源 0.8s 起步，两步注入的窗口从毫秒被拉宽到秒级）、② 把 jmcomic 客户端那 400 多个
        内部方法整套暴露给页面。名字带下划线，两条一起没了。
        """
        with self._client_lock:
            if self._client is None:
                self._client = JmOption.default().new_jm_client()
            return self._client

    def _warm_client(self) -> None:
        """后台预热图源连接；连不上就算了，等页面自己重试"""
        try:
            self._jm
        except Exception as e:
            print(f"[warmup] 图源没连上，交给页面重试: {e}", flush=True)

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

        with _db(DATA_DB) as conn:
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
            # 收藏是纯本地表：不碰图源账号，所以放 data/（清缓存不会连它一起删掉）。
            # 封面地址只在"加收藏"那一刻存一份，图源换线路后可能失效，当兜底用。
            conn.execute(
                "CREATE TABLE IF NOT EXISTS favorite ("
                "album_id TEXT PRIMARY KEY, "
                "title TEXT NOT NULL DEFAULT '', "
                "cover_url TEXT NOT NULL DEFAULT '', "
                "added_at REAL NOT NULL)"
            )
            # 搜索记录也搬进 data/（原来是 localStorage）：推荐要知道"搜过什么、几次、
            # 什么时候搜的"，这三样只有后端算得了 —— 前端那份只有关键词，没有次数与时间
            conn.execute(
                "CREATE TABLE IF NOT EXISTS search_log ("
                "keyword TEXT PRIMARY KEY, "
                "scope TEXT NOT NULL DEFAULT 'site', "
                "hits INTEGER NOT NULL DEFAULT 1, "
                "at REAL NOT NULL)"
            )
            # 整本离线下载：话单 + 每话状态。这两张表也是 photo_id -> album_id 的映射，
            # 阅读器靠它知道"这一话有离线副本"（cache 之外的目录，清缓存不动它）。
            conn.execute(
                "CREATE TABLE IF NOT EXISTS download_album ("
                "album_id TEXT PRIMARY KEY, "
                "title TEXT NOT NULL DEFAULT '', "
                "cover_url TEXT NOT NULL DEFAULT '', "
                "total INTEGER NOT NULL DEFAULT 0, "
                "done INTEGER NOT NULL DEFAULT 0, "
                "state TEXT NOT NULL DEFAULT 'queued', "
                "error TEXT NOT NULL DEFAULT '', "
                "added_at REAL NOT NULL, "
                "updated_at REAL NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS download_chapter ("
                "album_id TEXT NOT NULL, "
                "photo_id TEXT NOT NULL, "
                "index_no TEXT NOT NULL DEFAULT '', "
                "title TEXT NOT NULL DEFAULT '', "
                "state TEXT NOT NULL DEFAULT 'queued', "
                "total INTEGER NOT NULL DEFAULT 0, "
                "done INTEGER NOT NULL DEFAULT 0, "
                "updated_at REAL NOT NULL, "
                "PRIMARY KEY (album_id, photo_id))"
            )
            # 阅读器手里只有 photo_id，这张索引就是它反查"这一话属于哪个本子"的那条路
            conn.execute(
                "CREATE INDEX IF NOT EXISTS download_chapter_photo"
                " ON download_chapter (photo_id)"
            )
        # 老库升级：收藏行的 tag / 作者快照是后加的列，缺了当场补
        self._ensure_columns("favorite", {
            "tags_json": "TEXT NOT NULL DEFAULT '[]'",
            "authors_json": "TEXT NOT NULL DEFAULT '[]'",
        })
        with _db(CACHE_DB) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta_cache ("
                "key TEXT PRIMARY KEY, "
                "data_json TEXT NOT NULL, "
                "fetched_at REAL NOT NULL)"
            )
        self._move_legacy_cache()
        # 下载目录也先建出来。建不出来只报一声：别让一个路径问题把开窗挡住
        try:
            self._download_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"[download] 下载目录建不出来: {e}", flush=True)

    def _ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        """老库缺列就补上（新装的库由 CREATE TABLE 一次建全，这里只服务升级上来的库）"""
        with _db(DATA_DB) as conn:
            have = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, ddl in columns.items():
                if name not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def _move_legacy_cache(self) -> None:
        """把老库里的 meta_cache 表搬进 cache.db，然后删掉"""
        with _db(DATA_DB) as conn:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_cache'"
            ).fetchone()
            if exists is None:
                return
            rows = conn.execute("SELECT key, data_json, fetched_at FROM meta_cache").fetchall()
            if rows:
                with _db(CACHE_DB) as cache_conn:
                    cache_conn.executemany(
                        "INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at)"
                        " VALUES (?, ?, ?)",
                        rows,
                    )
            conn.execute("DROP TABLE meta_cache")

    def _cache_get(self, key: str, ttl: float) -> list | None:
        """命中且未过期返回数据，否则返回 None"""
        with _db(CACHE_DB) as conn:
            row = conn.execute(
                "SELECT data_json, fetched_at FROM meta_cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        data_json, fetched_at = row
        try:
            expired = time.time() - float(fetched_at) > ttl
        except (TypeError, ValueError):
            expired = True
        if expired:
            return None
        try:
            return json.loads(data_json)
        except ValueError:
            return None      # 内容坏了（手改过 / 老版本留下的）：当没命中，重新去取

    def _cache_set(self, key: str, data: list) -> None:
        with _db(CACHE_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at)"
                " VALUES (?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), time.time()),
            )

    def _cache_list(self, key: str, ttl: float) -> list | None:
        """
        同 _cache_get，但只认"一列"这种形状（文件名列表 / 榜单条目）。

        缓存里写的一直是 list；但库是本地明文，手改、老版本、迁移中断都可能留下别的形状，
        那种数据走到 `for name in files` 就会抛 TypeError 直穿到 JS 桥。这里当场判成"没命中"，
        大不了重新去图源取一次。
        """
        data = self._cache_get(key, ttl)
        return data if isinstance(data, list) else None

    def search(self, keyword: str, page: int = 1, scope: str = "site",
               order_by: str = "latest") -> list[dict[str, str]]:
        """
        搜索漫画，返回 [{"id", "title", "cover_url", "favorited"}]

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
        cached = self._cache_list(key, self._search_ttl)
        if cached is not None:
            return self._with_favorited(cached)
        try:
            result_page = getattr(self._jm, _SCOPE_MAP[scope])(
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
        return self._with_favorited(data)

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
        cached = self._cache_list(key, self._ranking_ttl)
        if cached is not None:
            return self._with_favorited(cached)
        mine, gate = self._fetch_guard(key)
        if not mine:
            gate.wait(self._inflight_wait)
            cached = self._cache_list(key, self._ranking_ttl)
            if cached is not None:
                return self._with_favorited(cached)
        try:
            try:
                result_page = self._jm.categories_filter(
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
        finally:
            if mine:
                self._fetch_done(key, gate)
        return self._with_favorited(data)
    
    def clear_cache(self) -> dict[str, int]:
        """清缓存：接口元数据 + 章节图；data/ 里的用户数据不动"""
        with _db(CACHE_DB) as conn:
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
            always = set(self._dl_photo_ids) | set(self._dl_pending)
        if self._last_photo_id:
            always.add(self._last_photo_id)
        with _db(DATA_DB) as conn:
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
        with _db(CACHE_DB) as conn:
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
            # 下载线程可能在这一瞬间改名 / 删文件，stat 会 OSError：这一趟不参与排序就行
            mtimes = []
            for f in folder.glob("*"):
                try:
                    if f.is_file():
                        mtimes.append(f.stat().st_mtime)
                except OSError:
                    pass
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
        if not isinstance(data, dict):
            data = None      # 形状不对就当没命中（缓存是本地明文库，可能被手改过）
        if data is None:
            try:
                album = self._jm.get_album_detail(album_id)
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
            self._backfill_favorite(album_id, data)   # 老收藏行缺快照，趁这次详情补上
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
        if isinstance(cached, dict):     # 形状不对就当没命中（见 _cache_list 的说明）
            return cached
        try:
            comment_page = self._jm.album_pagination(album_id, page=page)
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

    def get_forum(self, page: int = 1) -> dict:
        """
        论坛（全站评论流，只读、不需要登录），返回 {"total", "has_more", "items": [
        {"comment_id", "nickname", "content", "created_at", "spoiler", "reply",
         "reply_count", "album_id", "favorited"}]}

        album_id 为空串表示这条评论没挂本子；封面地址每次返回前现拼（域名会变），
        所以缓存里不放。服务端把 total 封在 5000（= 500 页），翻到顶就别再要了。
        """
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            raise ValueError("评论页码要是数字") from None
        key = f"forum:{page}"
        cached = self._cache_get(key, self._comment_ttl)
        if isinstance(cached, dict):
            return self._forum_out(cached)
        try:
            comment_page = self._jm.forum_pagination(page=page)
        except Exception as e:
            raise RuntimeError(f"论坛获取失败: {e}") from e
        items = []
        for cm in comment_page:
            album_id = str(cm.album_id or "").strip()
            if album_id == "0":
                album_id = ""
            items.append({
                "comment_id": str(cm.comment_id or ""),
                "nickname": cm.nickname or cm.username or "匿名",
                "content": cm.content or "",
                "created_at": cm.created_at or "",
                "spoiler": bool(cm.is_spoiler),
                "reply": cm.parent_comment_id is not None,
                "reply_count": len(cm.replies),   # 回评只报个数，不铺开
                "album_id": album_id,
            })
        page_count = comment_page.page_count
        data = {
            "total": int(comment_page.total or 0),
            # 满一页就当还有下一页；图源给了总页数就顺便按它封顶
            "has_more": len(items) >= comment_page.page_size
            and (page_count is None or page < page_count),
            "items": items,
        }
        self._cache_set(key, data)
        return self._forum_out(data)

    def _forum_out(self, data: dict) -> dict:
        """
        缓存里的论坛数据 -> 返回给前端：封面地址现拼（图源域名会变），收藏态也现拼
        （收藏 / 取消收藏就是本地一行记录，不能跟着有 TTL 的缓存一起老）。
        """
        favs = self._favorited_ids([item.get("album_id") or "" for item in data["items"]])
        return {
            **data,
            "items": [
                {
                    **item,
                    "cover_url": JmcomicText.get_album_cover_url(item["album_id"])
                    if item.get("album_id") else "",
                    "favorited": (item.get("album_id") or "") in favs,
                }
                for item in data["items"]
            ],
        }

    def get_album_titles(self, album_ids: list) -> dict:
        """
        批量把本子 ID 换成标题（论坛列表那排"来自《xxx》"用）。

        走的是 get_album_detail 那套缓存，等于顺手把详情页预热了；单个失败就当
        这个 ID 没有标题，不影响别的。一次最多 30 个，并发 5。
        """
        if not isinstance(album_ids, (list, tuple)):
            raise ValueError("本子 ID 要传列表")
        ids: list[str] = []
        for raw in album_ids[:30]:
            aid = str(raw).strip()
            if aid and aid not in ids:
                ids.append(aid)
        if not ids:
            return {}

        def one(aid: str) -> tuple[str, str]:
            try:
                return aid, self.get_album_detail(aid)["title"]
            except Exception:
                return aid, ""

        titles = {}
        with ThreadPoolExecutor(max_workers=min(5, len(ids))) as pool:
            for aid, title in pool.map(one, ids):
                if title:
                    titles[aid] = title
        return titles

    def prefetch_albums(self, album_ids: list) -> int:
        """
        列表铺完之后，后台把这几部的详情缓存拉好（详情里有 tag，留给以后的推荐用）。

        立刻返回"这次要去预热的条数"，真正的请求交给后台线程 —— 页面接下来的点击不能等它。
        已经预热过的（这次开窗期间记着）直接跳过，一次最多 self._pf_albums 个。
        """
        if self._pf_albums <= 0:
            return 0
        if not isinstance(album_ids, (list, tuple)):
            raise ValueError("本子 ID 要传列表")
        todo: list[str] = []
        for raw in album_ids:
            aid = str(raw).strip()
            if not aid or aid in todo or aid in self._prefetch_done:
                continue
            todo.append(aid)
        todo = todo[:self._pf_albums]
        if todo:
            # 先记账再起线程：首页几个分类先后铺好、连着来两次也只跑一次
            self._prefetch_done.update(todo)
            threading.Thread(target=self._prefetch_albums_run, args=(todo,), daemon=True).start()
        return len(todo)

    def _prefetch_albums_run(self, ids: list[str]) -> None:
        """后台预热详情；失败的不记账，下次进这一页再试"""
        failed: list[str] = []

        def one(aid: str) -> None:
            try:
                self.get_album_detail(aid)   # 缓存里有就只是读一次库
            except Exception:
                failed.append(aid)

        with ThreadPoolExecutor(max_workers=min(4, len(ids))) as pool:
            list(pool.map(one, ids))
        self._prefetch_done.difference_update(failed)

    def prefetch_chapter(self, photo_id: str) -> int:
        """
        后台把这一话"开头那几张"下下来：进详情页预热要读的那一话，阅读时预热下一话。

        立刻返回要下的张数（真的下载在后台线程里）。开头那几张已经在磁盘上就返回 0 ——
        之前看过的话本来就有缓存，不用再预加载。张数取 config 的 prefetch.chapter_images。
        """
        if self._pf_images <= 0:
            return 0
        photo_id = str(photo_id).strip()
        if not photo_id:
            raise ValueError("缺少章节 ID")
        if self._downloaded_chapter_dir(photo_id) is not None:
            return 0            # 有离线副本了，不用再往缓存里下
        img_dir = IMG_DIR / photo_id
        files = self._cache_list(f"photo:{photo_id}", self._photo_ttl)
        if files:
            head = files[:self._pf_images]
            if head and all((img_dir / name).exists() for name in head):
                return 0
        # 目录得自己建：get_chapter 进章节时会建，预加载这条路不走它，
        # 而 jmcomic 碰上不存在的目录是"静默不落盘"（请求照发、异常照吞、文件没有）
        img_dir.mkdir(parents=True, exist_ok=True)
        self._spawn_download(photo_id, None, self._pf_images)
        return self._pf_images

    def prefetch_home(self, time_range: str, order_by: str = "views") -> int:
        """
        闪屏期间把首页要的那批元数据先拉起来：hero + 各分类各一页 + 推荐段。

        立刻返回"这次要去拉几次"，真正的请求交给后台线程 —— 闪屏不等它。
        键必须和 board.ts 后面自己发的那些**完全一样**（ranking:{range}:{cat}:{order}:1），
        不然这次预热就白跑了：首页还是会走网络。两边前后脚撞上也没事，get_ranking 认在飞的。
        """
        if time_range not in _TIME_MAP:
            raise ValueError(f"未知榜单类型: {time_range}，应为 day/week/month")
        if order_by not in _ORDER_BY_MAP:
            raise ValueError(f"未知排序: {order_by}")
        cats = list(_CATEGORY_MAP)
        threading.Thread(
            target=self._prefetch_home_run, args=(time_range, order_by, cats), daemon=True
        ).start()
        return len(cats) + 1     # 各分类各一页 + 推荐段

    def _prefetch_home_run(self, time_range: str, order_by: str, cats: list[str]) -> None:
        """后台把首页那几页拉进缓存；单条失败就算了，页面自己还会再要一次"""

        def quiet(fn) -> None:
            try:
                fn()
            except Exception:
                pass

        # 全部并发（各分类 + 推荐段）：排成好几批的话，等它的首页反而比自己拉还慢
        with ThreadPoolExecutor(max_workers=min(8, len(cats) + 1)) as pool:
            for cat in cats:
                pool.submit(quiet, partial(self.get_ranking, time_range, cat, 1, order_by))
            pool.submit(quiet, partial(self.get_recommendations, "home"))

    def _fetch_guard(self, key: str) -> tuple[bool, threading.Event]:
        """
        同一把钥匙同一时刻只让一个线程去图源取。

        返回 (轮到我了没, 事件)：轮到我，取完（成功失败都算）必须 _fetch_done()；
        轮不到我，等事件等到超时，然后自己再读一次缓存 —— 还是空就自己取。
        """
        with self._inflight_lock:
            gate = self._inflight.get(key)
            if gate is None:
                gate = threading.Event()
                self._inflight[key] = gate
                return True, gate
            return False, gate

    def _fetch_done(self, key: str, gate: threading.Event) -> None:
        with self._inflight_lock:
            self._inflight.pop(key, None)
        gate.set()

    def _start_img_server(self) -> str:
        """
        启动本地图片静态服务（只监听本机），返回 base url。

        两个根：/images/... 走 cache（随手补下的），/downloads/... 走 download.dir（离线副本）。
        下载目录是开窗时从配置读的，所以在这儿交给 handler —— 改了 download.dir 要重开窗口。
        """
        class _Handler(_QuietHandler):
            extra_roots = {"/downloads": self._download_dir}

        handler = partial(_Handler, directory=str(CACHE_DIR))
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

        # 这一话有离线副本就整话走下载目录：既不往缓存里下第二遍，也不怕缓存被清
        offline = self._downloaded_chapter_dir(photo_id)

        key = f"photo:{photo_id}"
        files: list[str] | None = self._cache_list(key, self._photo_ttl)

        if files is None:
            try:
                photo = self._jm.get_photo_detail(photo_id)
            except Exception as e:
                raise RuntimeError(f"章节获取失败: {e}") from e
            files = [_img_name(img) for img in photo]
            self._cache_set(key, files)
            if offline is None:
                missing = [
                    (img, img_dir / name)
                    for img, name in zip(photo, files)
                    if not (img_dir / name).exists()
                ]
                if missing:
                    self._spawn_download(photo_id, missing)
        elif offline is None and any(not (img_dir / name).exists() for name in files):
            # 列表命中缓存、图还没下全：把取详情那次网络请求也挪到后台，别拖慢这次返回
            self._spawn_download(photo_id, None)

        if offline is not None:
            album_id, folder = offline
            if all((folder / name).exists() for name in files):
                return {
                    "photo_id": photo_id,
                    "images": [
                        f"{self.img_base}/downloads/{album_id}/{photo_id}/{name}"
                        for name in files
                    ],
                }

        return {
            "photo_id": photo_id,
            "images": [f"{self.img_base}/images/{photo_id}/{name}" for name in files],
        }

    def _spawn_download(self, photo_id: str, jobs: list[tuple] | None,
                        limit: int | None = None) -> None:
        """
        起一个后台下载批次；jobs 为 None 表示要去网络取图列表（同一章节只跑一批）。
        limit 只下前几张（预加载用）；为 None 就是这一话缺多少下多少。
        """
        with self._dl_batch_lock:
            if photo_id in self._dl_photo_ids:
                # 已经有批次在跑：预加载那种"只下几张"并进去就行（更全的在后头）；
                # 但"要整话"的必须记一笔 —— 否则用户真进阅读器时那次请求被静默吃掉，
                # 剩下的图就永远下不下来（页面上一直转圈重试）。
                if limit is None:
                    self._dl_pending.add(photo_id)
                return
            self._dl_photo_ids.add(photo_id)
        threading.Thread(target=self._run_download, args=(photo_id, jobs, limit), daemon=True).start()

    def _run_download(self, photo_id: str, jobs: list[tuple] | None,
                      limit: int | None = None) -> None:
        again = False
        try:
            if jobs is None:
                img_dir = IMG_DIR / photo_id
                try:
                    photo = self._jm.get_photo_detail(photo_id)
                except Exception:
                    return  # 网络不通就留着下次进章节再补
                # 顺手把文件名列表也缓存了（get_chapter 也这么写）：预加载靠它判断
                # "开头那几张已经在磁盘上"，不用每次都去网络问一遍
                names = [_img_name(img) for img in photo]
                self._cache_set(f"photo:{photo_id}", names)
                jobs = [
                    (img, img_dir / name)
                    for img, name in zip(photo, names)
                    if not (img_dir / name).exists()
                ]
            if limit is not None:
                jobs = jobs[:limit]
            self._download_images(jobs)
        finally:
            with self._dl_batch_lock:
                self._dl_photo_ids.discard(photo_id)
                again = photo_id in self._dl_pending
                self._dl_pending.discard(photo_id)
            if again:
                self._spawn_download(photo_id, None)   # 这批期间有人要整话，补一次全的

    def _download_images(self, jobs: list[tuple]) -> None:
        """并发下载；每张图先写 .part 再改名，中断不留坏文件"""
        self._download_images_batched(jobs)

    def _download_images_batched(self, jobs: list[tuple],
                                pause: threading.Event | None = None) -> None:
        """
        并发下这些图，每批 workers 张。

        分批是为了"暂停"能很快生效：`with ThreadPoolExecutor` 会等已提交的任务跑完，
        一次全提交的话暂停得等整话下完（几十张）。批间检查一下，最多多下一批。
        """
        jobs = [(img, path) for img, path in jobs if not path.exists()]
        size = max(1, self._dl_workers)
        while jobs:
            if pause is not None and pause.is_set():
                return
            batch, jobs = jobs[:size], jobs[size:]
            with ThreadPoolExecutor(max_workers=size) as pool:
                list(pool.map(self._download_one_retry, batch))

    def _download_one_retry(self, job: tuple) -> bool:
        """单张图带重试；返回最终有没有拿到文件（退避一下，别按着刚抖的图源猛敲）"""
        attempts = self._dl_retries + 1
        for i in range(attempts):
            if self._download_one(job):
                return True
            if i + 1 < attempts:
                time.sleep(0.6 * (i + 1))
        return False

    def _download_one(self, job: tuple) -> bool:
        """下一张图；失败只删这张的 .part，已经下好的图不动（下次续传只补缺的）"""
        img, path = job
        if path.exists():
            return True
        # 临时名要保留真实后缀：jmcomic 按输出后缀定编码，用 .part 当后缀会直接抛错
        tmp = path.with_name(f"{path.stem}.part{path.suffix}")
        try:
            self._jm.download_by_image_detail(img, str(tmp))
            tmp.rename(path)
            return True
        except Exception:
            tmp.unlink(missing_ok=True)
            return False

    # ==================== 整本离线下载（data/app.db + download.dir） ====================
    # 一句话：进度就是磁盘上那些文件。续传时不看内存里的计数，只把缺的挑出来补 ——
    # 所以关窗、断电、图源抖，下次开窗都只下没下过的那部分。

    _DOWNLOAD_SELECT = (
        "SELECT a.album_id, a.title, a.cover_url, a.state, a.error, a.total, a.done,"
        " a.added_at, a.updated_at,"
        " COALESCE(s.images, 0), COALESCE(s.images_total, 0)"
        " FROM download_album a LEFT JOIN ("
        "   SELECT album_id, SUM(done) AS images, SUM(total) AS images_total"
        "   FROM download_chapter GROUP BY album_id) s ON s.album_id = a.album_id"
    )

    def start_download(self, album_id: str, title: str = "", cover_url: str = "",
                       chapters: list | None = None) -> dict:
        """
        开一个整本下载；已经在下的就把没见过的章节补进话单，不重头。

        chapters 是详情页手里那份 [{"photo_id", "index", "title"}]：用它就不用再拉一次详情。
        已经下完的话保持 done，不会被重下（换域名 / 补新章节都走这一条路）。
        """
        aid = self._need_album_id(album_id)
        if chapters is not None and not isinstance(chapters, (list, tuple)):
            raise ValueError("话单要传列表")     # 传个数字 / 字符串的话，for 出来的全是垃圾
        rows: list[tuple[str, str, str, str]] = []
        for item in chapters or []:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("photo_id") or "").strip()
            if not pid:
                continue
            rows.append((pid, aid, str(item.get("index") or ""), str(item.get("title") or "")))
        if not rows:
            raise ValueError("没有可下载的章节")

        now = time.time()
        with _db(DATA_DB) as conn:
            old = conn.execute(
                "SELECT added_at FROM download_album WHERE album_id = ?", (aid,)
            ).fetchone()
            added_at = old[0] if old else now     # 重开一次任务不改"第一次下载"的时间
            conn.execute(
                "INSERT OR REPLACE INTO download_album"
                " (album_id, title, cover_url, total, done, state, error, added_at, updated_at)"
                " VALUES (?, ?, ?, 0, 0, ?, '', ?, ?)",
                (aid, str(title or "").strip(), str(cover_url or ""), "queued", added_at, now),
            )
            # 已有的话保留原状态：下过的不重下，只把没见过的话加进来
            conn.executemany(
                "INSERT OR IGNORE INTO download_chapter"
                " (photo_id, album_id, index_no, title, state, total, done, updated_at)"
                " VALUES (?, ?, ?, ?, 'queued', 0, 0, ?)",
                [(pid, cid, idx, name, now) for pid, cid, idx, name in rows],
            )
        self._refresh_album_progress(aid)
        self._spawn_album_download(aid)
        return self.get_download(aid)

    def get_downloads(self) -> list[dict]:
        """所有下载任务，按最近更新倒序（我的下载页用）"""
        with _db(DATA_DB) as conn:
            rows = conn.execute(self._DOWNLOAD_SELECT + " ORDER BY a.updated_at DESC").fetchall()
        return [self._download_out(row) for row in rows]

    def get_download(self, album_id: str) -> dict | None:
        """单部漫画的下载任务（详情页按钮认状态用）；没下过返回 None"""
        aid = self._need_album_id(album_id)
        with _db(DATA_DB) as conn:
            row = conn.execute(
                self._DOWNLOAD_SELECT + " WHERE a.album_id = ?", (aid,)
            ).fetchone()
        return self._download_out(row) if row else None

    def pause_download(self, album_id: str) -> dict | None:
        """
        暂停下载。worker 在下一批（workers 张）之后退出，已经下好的图全留着，
        下次「继续下载」只补缺的。
        """
        aid = self._need_album_id(album_id)
        with self._album_dl_lock:
            pause = self._album_dl_pause.get(aid)
        if pause is not None:
            pause.set()
        self._refresh_album_progress(aid, state="paused")
        return self.get_download(aid)

    def resume_download(self, album_id: str) -> dict | None:
        """接着下（只补缺的那几话 / 那几张）；没下完的、报错的、暂停的都走它"""
        aid = self._need_album_id(album_id)
        self._spawn_album_download(aid)
        return self.get_download(aid)

    def remove_download(self, album_id: str, delete_files: bool = False) -> dict:
        """
        删掉一个下载任务；delete_files=True 时连离线副本一起删。

        正在下的先叫停：worker 最多再下一个批次就退出，这儿最多等 5 秒；
        等不到也照删（文件用 ignore_errors 硬删 —— Windows 上正被写的那张删不掉，
        留给下次清理，但任务记录一定会消失）。
        """
        aid = self._need_album_id(album_id)
        files = 0
        with self._album_dl_lock:
            self._album_dl_stop.setdefault(aid, threading.Event()).set()
            pause = self._album_dl_pause.get(aid)
            thread = self._album_dl_threads.get(aid)
        if pause is not None:
            pause.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        with _db(DATA_DB) as conn:
            conn.execute("DELETE FROM download_chapter WHERE album_id = ?", (aid,))
            conn.execute("DELETE FROM download_album WHERE album_id = ?", (aid,))
        if delete_files:
            folder = self._download_dir / aid
            if folder.is_dir():
                files = self._count_files(folder, True)
                shutil.rmtree(folder, ignore_errors=True)
        return {"removed": True, "files": files}

    # ---------- 内部：任务调度 ----------

    def _download_out(self, row: tuple) -> dict:
        """一行任务记录 -> 前端要的形状"""
        album_id = str(row[0])
        state = str(row[3])
        return {
            "album_id": album_id,
            "title": row[1],
            "cover_url": row[2],
            "state": state,
            "error": row[4],
            "total": int(row[5]),
            "done": int(row[6]),
            "images_done": int(row[9]),
            "images_total": int(row[10]),
            "added_at": row[7],
            "updated_at": row[8],
            # 阅读进度现拼：跟「最近阅读」同一个口径（同一张 history 表），不进任何缓存
            "read": self.get_album_progress(album_id),
            "running": state in ("queued", "running"),
        }

    def _refresh_album_progress(self, album_id: str, state: str | None = None,
                                error: str | None = None) -> None:
        """把 total / done 按话单重算一遍，顺带改 state / error（任务被删了就是空操作）"""
        total, done = self._chapter_counts(album_id)
        sets = ["total = ?", "done = ?", "updated_at = ?"]
        args: list[Any] = [total, done, time.time()]
        if state is not None:
            sets.append("state = ?")
            args.append(state)
        if error is not None:
            sets.append("error = ?")
            args.append(error)
        args.append(album_id)
        with _db(DATA_DB) as conn:
            conn.execute(f"UPDATE download_album SET {', '.join(sets)} WHERE album_id = ?", args)

    def _chapter_counts(self, album_id: str) -> tuple[int, int]:
        """(话数, 已下完的话数)"""
        with _db(DATA_DB) as conn:
            row = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN state = 'done' THEN 1 ELSE 0 END)"
                " FROM download_chapter WHERE album_id = ?",
                (album_id,),
            ).fetchone()
        return int(row[0] or 0), int(row[1] or 0)

    def _pending_chapters(self, album_id: str) -> list[str]:
        """
        这轮要下哪些话，按话单顺序。

        没下完的（含上次出错的那几话）都要；已经标 done 的再量一下磁盘 ——
        续传时数据可能被清掉 / 挪走过，量一次才知道要不要补（一次目录扫描，很便宜）。
        """
        with _db(DATA_DB) as conn:
            rows = conn.execute(
                "SELECT photo_id, state, total FROM download_chapter"
                " WHERE album_id = ? ORDER BY rowid",
                (album_id,),
            ).fetchall()
        pending: list[str] = []
        for photo_id, state, total in rows:
            pid = str(photo_id)
            if state != 'done':
                pending.append(pid)
            elif int(total or 0) > 0 and \
                    self._count_files(self._download_dir / album_id / pid) < int(total):
                pending.append(pid)
        return pending

    def _set_chapter_state(self, album_id: str, photo_id: str, state: str,
                           done: int, total: int) -> None:
        with _db(DATA_DB) as conn:
            conn.execute(
                "UPDATE download_chapter SET state = ?, done = ?, total = ?, updated_at = ?"
                " WHERE album_id = ? AND photo_id = ?",
                (state, int(done), int(total), time.time(), album_id, str(photo_id)),
            )

    def _album_stopped(self, album_id: str) -> bool:
        """任务被删了？（worker 见到就立刻收手，别再往库里写、别再下）"""
        with self._album_dl_lock:
            stop = self._album_dl_stop.get(album_id)
        return stop is not None and stop.is_set()

    def _spawn_album_download(self, album_id: str) -> None:
        """起整本下载线程；同一本只跑一个（在跑就什么都不做）"""
        with self._album_dl_lock:
            thread = self._album_dl_threads.get(album_id)
            if thread is not None and thread.is_alive():
                return
            self._album_dl_stop.pop(album_id, None)     # 上次删过就翻篇
            pause = self._album_dl_pause.setdefault(album_id, threading.Event())
            pause.clear()
            thread = threading.Thread(
                target=self._run_album_download, args=(album_id, pause), daemon=True
            )
            self._album_dl_threads[album_id] = thread
        self._refresh_album_progress(album_id, state="queued", error="")
        thread.start()

    def _run_album_download(self, album_id: str, pause: threading.Event) -> None:
        """
        整本下载：逐话串行，一话内部并发。

        某一话彻底失败（重试完还没有）只把这话标 error，整本继续 —— 一话卡住不该
        让后面几十话都下不了；用户点「继续下载」时再补它。
        """
        self._refresh_album_progress(album_id, state="running", error="")
        attempted: set[str] = set()
        try:
            # 外层再转一圈是为了"下到一半又补了新话"：新话在下一圈会被捞上来。
            # attempted 保证一话这一轮只试一次 —— 失败的留给下次「继续下载」，别在这儿死磕。
            while not pause.is_set() and not self._album_stopped(album_id):
                todo = [pid for pid in self._pending_chapters(album_id) if pid not in attempted]
                if not todo:
                    break
                for photo_id in todo:
                    if pause.is_set() or self._album_stopped(album_id):
                        break
                    attempted.add(photo_id)
                    ok, done, total = self._download_chapter_to_dir(album_id, photo_id, pause)
                    if self._album_stopped(album_id):
                        break                # 任务已经被删了，别再写库
                    self._set_chapter_state(album_id, photo_id, "done" if ok else "error", done, total)
                    self._refresh_album_progress(album_id)
        finally:
            with self._album_dl_lock:
                # 只清自己那几条：这期间用户可能又开了一个新任务
                if self._album_dl_threads.get(album_id) is threading.current_thread():
                    self._album_dl_threads.pop(album_id, None)
                    self._album_dl_pause.pop(album_id, None)
            if not self._album_stopped(album_id):
                self._finish_album_state(album_id, pause)

    def _finish_album_state(self, album_id: str, pause: threading.Event) -> None:
        """跑完了 / 暂停了 / 还有话没下完，各自落一个终态"""
        total, done = self._chapter_counts(album_id)
        if total and done >= total:
            self._refresh_album_progress(album_id, state="done", error="")
        elif pause.is_set():
            self._refresh_album_progress(album_id, state="paused")
        else:
            left = total - done
            self._refresh_album_progress(
                album_id, state="error",
                error=f"{left} 话没下完，点「继续下载」接着补",
            )

    def _download_chapter_to_dir(self, album_id: str, photo_id: str,
                                 pause: threading.Event) -> tuple[bool, int, int]:
        """
        把这一话下到 <download.dir>/<album_id>/<photo_id>/，返回 (是否完整, 已下, 总数)。

        文件名列表先看缓存（`photo:<id>` 只存文件名）：续传时那些下过的话连一次
        网络请求都不用发 —— 这才是"按进度重新下载"最省的那条路。
        """
        folder = self._download_dir / album_id / photo_id
        names = self._cache_list(f"photo:{photo_id}", self._photo_ttl)
        if names and all((folder / name).exists() for name in names):
            return True, len(names), len(names)
        try:
            photo = self._jm.get_photo_detail(photo_id)
        except Exception:
            return False, self._count_files(folder), len(names or [])
        files = [_img_name(img) for img in photo]
        self._cache_set(f"photo:{photo_id}", files)   # 下次续传就能跳过已下完的话
        # 目录得自己建：jmcomic 碰上不存在的目录是"静默不落盘"（请求照发、异常照吞、文件没有）
        folder.mkdir(parents=True, exist_ok=True)
        pairs = list(zip(photo, files))
        jobs = [(img, folder / name) for img, name in pairs if not (folder / name).exists()]
        self._download_images_batched(jobs, pause)
        missing = [name for _img, name in pairs if not (folder / name).exists()]
        return (not missing), len(files) - len(missing), len(files)

    def _count_files(self, folder: Path, recursive: bool = False) -> int:
        """目录里真正下好的图片张数（.part 不算 —— 它是写了一半的）"""
        if not folder.is_dir():
            return 0
        items = folder.rglob("*") if recursive else folder.glob("*")
        return sum(1 for f in items if f.is_file() and ".part" not in f.name)

    def _downloaded_chapter_dir(self, photo_id: str) -> tuple[str, Path] | None:
        """这一话有下完的离线副本就返回 (album_id, 目录)，否则 None"""
        with _db(DATA_DB) as conn:
            row = conn.execute(
                "SELECT album_id FROM download_chapter"
                " WHERE photo_id = ? AND state = 'done' LIMIT 1",
                (str(photo_id),),
            ).fetchone()
        if row is None:
            return None
        folder = self._download_dir / str(row[0]) / str(photo_id)
        return (str(row[0]), folder) if folder.is_dir() else None

    def _resume_downloads_loop(self) -> None:
        """
        开窗几秒后把没下完的接着下。

        `running` 也算没下完：上次是被关窗 / 断电打断的，进程一停状态就停在 running 上。
        """
        time.sleep(5)      # 先让首屏把要的数据拿到，别一开机就跟首页抢带宽
        try:
            with _db(DATA_DB) as conn:
                rows = conn.execute(
                    "SELECT album_id FROM download_album WHERE state IN ('queued', 'running')"
                ).fetchall()
            for (album_id,) in rows:
                self._spawn_album_download(str(album_id))
            if rows:
                print(f"[download] 续传 {len(rows)} 个任务", flush=True)
        except Exception as e:
            print(f"[download] 续传失败: {e}", flush=True)

    def save_progress(self, album_id: str, photo_id: str, page_index: int,
                    title: str = "", cover_url: str = "") -> None:
        """保存阅读进度；title/cover_url 给首页"继续阅读"列表展示用"""
        # 页码与文本都先归一：title / cover_url 那两列是 NOT NULL，前端漏给一个 null
        # 就会撞 IntegrityError —— 这一话的真实进度反而丢了
        try:
            page = max(0, int(page_index))
        except (TypeError, ValueError):
            page = 0
        with _db(DATA_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO history"
                " (album_id, photo_id, page_index, title, cover_url, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (str(album_id), str(photo_id), page,
                str(title or ""), str(cover_url or ""), time.time()),
            )

    def get_progress(self, album_id: str, photo_id: str) -> int:
        """返回上次看到的页码（从 0 开始），没有记录返回 0"""
        with _db(DATA_DB) as conn:
            row = conn.execute(
                "SELECT page_index FROM history WHERE album_id=? AND photo_id=?",
                (str(album_id), str(photo_id)),
            ).fetchone()
        return int(row[0]) if row else 0

    def get_history(self, limit: int = 10) -> list[dict]:
        """最近阅读：一部漫画一条，取最近读的那一话，按更新时间倒序"""
        # 夹一下范围：sqlite 里负数 LIMIT 是"不限制"，等于绕过上限
        limit = _cfg_int(limit, 10, 1, 500)
        with _db(DATA_DB) as conn:
            rows = conn.execute(
                "SELECT album_id, photo_id, page_index, title, cover_url, updated_at FROM ("
                " SELECT *, ROW_NUMBER() OVER (PARTITION BY album_id ORDER BY updated_at DESC) AS rn"
                " FROM history) WHERE rn = 1 ORDER BY updated_at DESC LIMIT ?",
                (limit,),
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
        with _db(DATA_DB) as conn:
            row = conn.execute(
                "SELECT photo_id, page_index, title FROM history"
                " WHERE album_id = ? ORDER BY updated_at DESC LIMIT 1",
                (str(album_id),),
            ).fetchone()
        if row is None:
            return None
        return {"photo_id": row[0], "page_index": int(row[1]), "title": row[2]}

    @staticmethod
    def _need_album_id(album_id: Any) -> str:
        """收藏系列接口的入参校验：漫画 ID 必须是非空串"""
        if album_id is None:              # str(None) 会变成 "None"，得先挡掉
            raise ValueError("缺少漫画 ID")
        aid = str(album_id).strip()
        if not aid:
            raise ValueError("缺少漫画 ID")
        return aid

    def is_favorite(self, album_id: str) -> bool:
        """这部漫画在本地收藏里吗（只查本地表，不看图源账号）"""
        aid = self._need_album_id(album_id)
        with _db(DATA_DB) as conn:
            row = conn.execute(
                "SELECT 1 FROM favorite WHERE album_id = ?", (aid,)
            ).fetchone()
        return row is not None

    def toggle_favorite(self, album_id: str, title: str = "", cover_url: str = "",
                        tags: list | None = None, authors: list | None = None) -> bool:
        """
        切换收藏，返回切换后的状态（True = 已收藏）

        title / cover_url 只在"加入收藏"那一下用得上，收藏页列表靠它显示。
        tags / authors 是收藏那一刻的快照（详情页本来就拿着），推荐画像靠它 —— 详情缓存
        只有 24h，一周后拿缓存算画像就空了一半。没传 / 传空就回落详情缓存。
        收藏态故意不进 album 详情缓存（那个有 24h TTL），否则取消收藏后界面还显示已收藏。
        """
        aid = self._need_album_id(album_id)
        with _db(DATA_DB) as conn:
            exists = conn.execute(
                "SELECT 1 FROM favorite WHERE album_id = ?", (aid,)
            ).fetchone()
            if exists is not None:
                conn.execute("DELETE FROM favorite WHERE album_id = ?", (aid,))
                return False
            snap_tags, snap_authors = self._favorite_snapshot(aid, tags, authors)
            conn.execute(
                "INSERT OR REPLACE INTO favorite"
                " (album_id, title, cover_url, added_at, tags_json, authors_json)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (aid, str(title or "").strip(), str(cover_url or ""), time.time(),
                 json.dumps(snap_tags, ensure_ascii=False),
                 json.dumps(snap_authors, ensure_ascii=False)),
            )
            return True

    def remove_favorite(self, album_id: str) -> None:
        """取消收藏（收藏页的删除按钮用；本来就没收藏也不报错）"""
        aid = self._need_album_id(album_id)
        with _db(DATA_DB) as conn:
            conn.execute("DELETE FROM favorite WHERE album_id = ?", (aid,))

    def get_favorites(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """收藏列表，按收藏时间倒序；cover_url 是收藏那一刻的快照"""
        limit = _cfg_int(limit, 100, 1, 500)
        offset = _cfg_int(offset, 0, 0, 1000000)
        with _db(DATA_DB) as conn:
            rows = conn.execute(
                "SELECT album_id, title, cover_url, added_at FROM favorite"
                " ORDER BY added_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            # favorited 恒为 True：整页都是收藏，字段照样给，免得前端要认两种形状
            {"album_id": r[0], "title": r[1], "cover_url": r[2], "added_at": r[3],
             "favorited": True}
            for r in rows
        ]

    # ==================== 搜索记录（data/app.db） ====================
    # 推荐要知道"搜过什么、搜了几次、什么时候搜的" —— 只在前端记关键词不够用，
    # 所以从 localStorage 搬进 data/（跟收藏一个待遇：清缓存不动它）。
    _SEARCH_LOG_MAX = 200      # 表最多留这么多条，再往前的自然衰减掉，也免得表无限长

    def log_search(self, keyword: str, scope: str = "site") -> None:
        """记一次搜索：同一个词（不分大小写）次数 +1，时间刷成最新"""
        kw = str(keyword or "").strip()
        if not kw:
            return
        scope = scope if scope in _SCOPE_MAP else "site"
        now = time.time()
        with _db(DATA_DB) as conn:
            row = conn.execute(
                "SELECT keyword FROM search_log WHERE keyword = ? COLLATE NOCASE", (kw,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO search_log (keyword, scope, hits, at) VALUES (?, ?, 1, ?)",
                    (kw, scope, now),
                )
            else:
                # 存着的是第一次那个写法：第二次搜 "ABC" 不该在记录里多出一条
                conn.execute(
                    "UPDATE search_log SET hits = hits + 1, at = ?, scope = ? WHERE keyword = ?",
                    (now, scope, row[0]),
                )
            conn.execute(
                "DELETE FROM search_log WHERE keyword NOT IN ("
                " SELECT keyword FROM search_log ORDER BY at DESC LIMIT ?)",
                (self._SEARCH_LOG_MAX,),
            )

    def get_search_log(self, limit: int = 12) -> list[dict]:
        """最近搜索（时间倒序）：搜索页那排 chips 用，也是画像里搜索信号的来源"""
        limit = _cfg_int(limit, 12, 1, 100)
        with _db(DATA_DB) as conn:
            rows = conn.execute(
                "SELECT keyword, scope, hits, at FROM search_log ORDER BY at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"keyword": r[0], "scope": r[1], "hits": int(r[2]), "at": r[3]}
            for r in rows
        ]

    def remove_search_log(self, keyword: str) -> None:
        """删一条（chips 上的 ✕）；本来就没有也不报错"""
        kw = str(keyword or "").strip()
        if not kw:
            return
        with _db(DATA_DB) as conn:
            conn.execute("DELETE FROM search_log WHERE keyword = ? COLLATE NOCASE", (kw,))

    def clear_search_log(self) -> None:
        """清空（chips 右上那个「清空」）"""
        with _db(DATA_DB) as conn:
            conn.execute("DELETE FROM search_log")

    # ==================== 收藏态现拼 ====================

    def _favorited_ids(self, album_ids: list) -> set[str]:
        """这些 ID 里哪几个在本地收藏表里（一次查完，别逐个查）"""
        ids: list[str] = []
        for raw in album_ids:
            aid = str(raw or "").strip()
            if aid and aid not in ids:
                ids.append(aid)
        if not ids:
            return set()
        ids = ids[:500]      # sqlite 的变量上限是 999，面板不会这么大，防一手
        marks = ",".join("?" * len(ids))
        with _db(DATA_DB) as conn:
            rows = conn.execute(
                f"SELECT album_id FROM favorite WHERE album_id IN ({marks})", ids
            ).fetchall()
        return {row[0] for row in rows}

    def _with_favorited(self, albums: list[dict]) -> list[dict]:
        """
        返回前现拼收藏态（跟现拼封面一个路子）：收藏 / 取消收藏就是本地一行记录，
        不能跟着有 TTL 的缓存一起老 —— 否则刚收藏完，列表里还是没角标。
        """
        if not albums:
            return albums
        favs = self._favorited_ids(
            [item.get("id") or item.get("album_id") or "" for item in albums]
        )
        return [
            {**item, "favorited": str(item.get("id") or item.get("album_id") or "") in favs}
            for item in albums
        ]

    # ==================== 画像 / 推荐 ====================
    # 一期只用「收藏 + 搜索」两种信号（隐式反馈用户砍了），画像每次现算、不落盘。
    # 打分只要 tag 与作者，来源是本地详情缓存 —— 这条路上绝对不发请求。

    def _cached_names(self, album_id: str) -> tuple[list[str], list[str]]:
        """本地详情缓存里的 tag / 作者；没缓存（或过期了）就返回空，不去网络取"""
        data = self._cache_get(f"album:v2:{album_id}", self._album_ttl)
        if not isinstance(data, dict):
            return [], []
        return list(data.get("tags") or []), list(data.get("authors") or [])

    def _favorite_snapshot(self, album_id: str, tags: list | None,
                           authors: list | None) -> tuple[list[str], list[str]]:
        """加收藏要存的 tag / 作者：以传进来的为准，没传就用详情缓存里那份"""
        def clean(raw: Any) -> list[str]:
            out: list[str] = []
            for item in (raw or []):
                name = str(item or "").strip()
                if name and name not in out:
                    out.append(name)
            return out

        snap_tags, snap_authors = clean(tags), clean(authors)
        if not snap_tags or not snap_authors:
            cached_tags, cached_authors = self._cached_names(album_id)
            snap_tags = snap_tags or cached_tags
            snap_authors = snap_authors or cached_authors
        return snap_tags, snap_authors

    def _backfill_favorite(self, album_id: str, detail: dict) -> None:
        """
        详情拉回来时顺手给"没有快照的老收藏行"补上（WHERE 命中不了就只是个空操作）。
        新装的库 / 新加的收藏都自带快照，这里只为升级上来的老库兜一次底。
        """
        try:
            with _db(DATA_DB) as conn:
                conn.execute(
                    "UPDATE favorite SET tags_json = ?, authors_json = ?"
                    " WHERE album_id = ? AND tags_json = '[]'",
                    (json.dumps(list(detail.get("tags") or []), ensure_ascii=False),
                     json.dumps(list(detail.get("authors") or []), ensure_ascii=False),
                     album_id),
                )
        except sqlite3.Error:
            pass    # 补快照失败不该影响"看详情"这件事

    def _taste_profile(self) -> dict:
        """
        现算画像，返回 {"tags": {tag: 权重}, "authors": {...}, "favorites": n, "searches": n}

        收藏每部给它的 tag / 作者各 +1.0（快照在 favorite.tags_json / authors_json）；
        搜索每个词 +0.6 × 次数，关键词同时当 tag 与作者字符串参与匹配
        （「中文」本来就是标签，搜作者名就命中作者维度，搜作品名两边都不命中、天然无害）。
        时间按 recommend.half_life_days 衰减，各自归一化后只留 top 20 tag + top 10 作者。
        """
        now = time.time()
        half_life = max(1, self._rc_half_life)
        tags: dict[str, float] = {}
        authors: dict[str, float] = {}

        def decay(at: Any) -> float:
            try:
                stamp = float(at)
            except (TypeError, ValueError):
                return 1.0
            age_days = max(0.0, (now - stamp) / 86400)
            return 0.5 ** (age_days / half_life)

        def add(bucket: dict[str, float], name: Any, weight: float) -> None:
            text = str(name or "").strip()
            if text:
                bucket[text] = bucket.get(text, 0.0) + weight

        def parse(raw: Any) -> list[str]:
            if not isinstance(raw, str):
                return []
            try:
                value = json.loads(raw)
            except ValueError:
                return []
            return [str(x).strip() for x in value if str(x).strip()] if isinstance(value, list) else []

        with _db(DATA_DB) as conn:
            favs = conn.execute(
                "SELECT album_id, added_at, tags_json, authors_json FROM favorite"
            ).fetchall()
            logs = conn.execute("SELECT keyword, hits, at FROM search_log").fetchall()

        for album_id, added_at, tags_json, authors_json in favs:
            weight = decay(added_at)
            fav_tags, fav_authors = parse(tags_json), parse(authors_json)
            if not fav_tags or not fav_authors:    # 老行还没快照：回落详情缓存（可能也没有）
                cached_tags, cached_authors = self._cached_names(str(album_id))
                fav_tags = fav_tags or cached_tags
                fav_authors = fav_authors or cached_authors
            for name in fav_tags:
                add(tags, name, weight)
            for name in fav_authors:
                add(authors, name, weight)

        for keyword, hits, at in logs:
            weight = 0.6 * max(1, int(hits or 1)) * decay(at)
            add(tags, keyword, weight)
            add(authors, keyword, weight)

        def keep(bucket: dict[str, float], top: int) -> dict[str, float]:
            """归一化到 0~1 并截断；排序固定（权重降序、同权重按名字），保证同样输入同样输出"""
            if not bucket:
                return {}
            best = max(bucket.values())
            if best <= 0:
                return {}
            ranked = sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
            return {name: weight / best for name, weight in ranked}

        return {
            "tags": keep(tags, 20),
            "authors": keep(authors, 10),
            "favorites": len(favs),
            "searches": sum(max(1, int(row[1] or 1)) for row in logs),
        }

    def get_taste_profile(self) -> dict:
        """画像长什么样：调算法用（以后设置页可以拿它显示"算法记住的 tag 与作者"）"""
        prof = self._taste_profile()
        return {
            "tags": [{"tag": name, "weight": round(w, 4)} for name, w in prof["tags"].items()],
            "authors": [{"author": name, "weight": round(w, 4)}
                        for name, w in prof["authors"].items()],
            "favorites": prof["favorites"],
            "searches": prof["searches"],
        }

    def _candidate_pool(self) -> list[dict[str, str]]:
        """
        候选池 = 周榜「全部」按观看的前 recommend.candidates 部。

        走的是 get_ranking 那一套缓存（首页本来就在拉这个榜），所以冷缓存时也最多多要一页；
        图源一页给多少条不定，凑不满就再要一页，最多三页。候选池大小只影响覆盖度，不影响速度。
        """
        want = self._rc_candidates
        pool: list[dict[str, str]] = []
        seen: set[str] = set()
        for page in (1, 2, 3):
            if len(pool) >= want:
                break
            try:
                got = self.get_ranking("week", "all", page)
            except Exception:
                break        # 榜单拉不动就用手上这些（一条都没有就是空池，前端整段藏起来）
            if not got:
                break
            for item in got:
                if item["id"] not in seen:
                    seen.add(item["id"])
                    pool.append(item)
        return pool[:want]

    def _rec_reason(self, tags: list[str], authors: list[str],
                    prof_tags: dict[str, float], prof_authors: dict[str, float]) -> str:
        """卡片副标题：说清"为什么推这部"（最多两项），一个都没命中就空着"""
        hits: list[tuple[float, str]] = [
            (prof_tags[name], name) for name in tags if name in prof_tags
        ]
        hits += [
            (prof_authors[name] * self._rc_author_boost, f"作者：{name}")
            for name in authors if name in prof_authors
        ]
        hits.sort(key=lambda item: (-item[0], item[1]))
        return " · ".join(text for _, text in hits[:2])

    def get_recommendations(self, kind: str = "home", limit: int | None = None,
                           exclude: list | None = None) -> dict:
        """
        推荐一批漫画，返回 {"cold": bool, "items": [
        {"id", "title", "cover_url", "subtitle", "favorited", "score"}]}

        候选池取热度榜，用「收藏 + 搜索」攒出来的 tag / 作者画像打分；没命中的候选只吃热度分，
        所以画像为空、或者一个都没命中时就是热度排序，此时 cold=True（界面该写「热门推荐」）。
        exclude 里的 ID 不参与（首页那个「换一批」）；kind 一期不影响结果 —— 首页与搜索页
        同一套（用户口径：搜索页不吃本次关键词），留着参数是为二期分叉。
        limit 传 None 用配置里的 recommend.limit；0 = 关掉推荐，返回空。
        """
        if kind not in ("home", "search"):
            raise ValueError(f"未知推荐位置: {kind}")
        want = self._rc_limit if limit is None else _cfg_int(limit, 0, 0, 50)
        if want <= 0:
            return {"cold": True, "items": []}
        pool = self._candidate_pool()
        if not pool:
            return {"cold": True, "items": []}

        # exclude 是页面自己传的（"这几部上面已经出现过了"）；不是列表就当没传，
        # 别为一个参数形状把整段推荐打掉
        if not isinstance(exclude, (list, tuple, set)):
            exclude = []
        skip = {str(raw).strip() for raw in exclude}
        prof = self._taste_profile()
        prof_tags, prof_authors = prof["tags"], prof["authors"]

        scored: list[tuple[float, dict]] = []
        best_match = 0.0
        for rank, item in enumerate(pool):
            if item["id"] in skip:
                continue
            hot = 1 - rank / len(pool)      # 池内归一的热度（名次越靠前越大）
            tags, authors = self._cached_names(item["id"])
            match = 0.0
            if tags or authors:
                hit = sum(prof_tags.get(name, 0.0) for name in tags)
                hit += self._rc_author_boost * sum(
                    prof_authors.get(name, 0.0) for name in authors)
                match = hit / (1 + len(tags)) ** 0.5   # 除以 sqrt(1+标签数)：标签多的别白占便宜
            best_match = max(best_match, match)
            score = (1 - self._rc_hot) * match + self._rc_hot * hot
            scored.append((score, {
                "id": item["id"],
                "title": item["title"],
                "cover_url": item["cover_url"],
                "subtitle": self._rec_reason(tags, authors, prof_tags, prof_authors),
                "score": round(score, 4),
            }))

        # 同分保持池内顺序（热度高的在前），不加抖动：同样的画像 + 同样的池子给同样的结果
        scored.sort(key=lambda pair: pair[0], reverse=True)
        items = self._with_favorited([item for _, item in scored[:want]])
        return {"cold": best_match <= 0, "items": items}

    def get_settings(self) -> dict:
        """当前配置（含默认值）"""
        return load_config()

    def save_settings(self, settings: dict) -> dict:
        """保存设置到 config.yaml 并返回完整配置（重启生效的项由前端提示）"""
        if not isinstance(settings, dict):
            raise RuntimeError("保存失败：设置内容格式不对")
        cfg = load_config()
        try:
            win = _setting_section(settings, "window", "窗口")
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

            dev = _setting_section(settings, "dev", "启动")
            if "url" in dev:
                url = str(dev["url"]).strip()
                if not url.startswith(("http://", "https://", "file://")):
                    raise ValueError("启动地址要以 http:// 或 https:// 或 file:// 开头")
                cfg["dev"]["url"] = url
            if "debug" in dev:
                cfg["dev"]["debug"] = bool(dev["debug"])
            if "use_dev_server" in dev:
                cfg["dev"]["use_dev_server"] = bool(dev["use_dev_server"])

            srv = _setting_section(settings, "server", "本地服务")
            if "port" in srv:
                cfg["server"]["port"] = _setting_int(srv["port"], 1024, 65535, "本地服务端口")

            reader = _setting_section(settings, "reader", "阅读器")
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

            detail = _setting_section(settings, "detail", "详情页")
            if "chapters_collapse" in detail:
                cfg["detail"]["chapters_collapse"] = _setting_int(
                    detail["chapters_collapse"], 0, 500, "章节折叠阈值")
            if "comment_preview" in detail:
                cfg["detail"]["comment_preview"] = _setting_int(
                    detail["comment_preview"], 0, 50, "评论预览条数")

            prefetch = _setting_section(settings, "prefetch", "预加载")
            if "albums" in prefetch:
                cfg["prefetch"]["albums"] = _setting_int(prefetch["albums"], 0, 30, "预加载详情条数")
            if "chapter_images" in prefetch:
                cfg["prefetch"]["chapter_images"] = _setting_int(
                    prefetch["chapter_images"], 0, 20, "预加载图片张数")
            if "next_at" in prefetch:
                cfg["prefetch"]["next_at"] = _setting_float(
                    prefetch["next_at"], 0, 1, "预加载下一话的进度比例")

            recommend = _setting_section(settings, "recommend", "推荐")
            if "limit" in recommend:
                cfg["recommend"]["limit"] = _setting_int(recommend["limit"], 0, 50, "推荐条数")
            if "candidates" in recommend:
                cfg["recommend"]["candidates"] = _setting_int(
                    recommend["candidates"], 5, 200, "推荐候选池大小")
            if "hot_weight" in recommend:
                cfg["recommend"]["hot_weight"] = _setting_float(
                    recommend["hot_weight"], 0, 1, "推荐里热度先验的占比")
            if "author_boost" in recommend:
                cfg["recommend"]["author_boost"] = _setting_float(
                    recommend["author_boost"], 0, 5, "作者命中的加成倍数")
            if "half_life_days" in recommend:
                cfg["recommend"]["half_life_days"] = _setting_int(
                    recommend["half_life_days"], 1, 365, "画像半衰期")

            download = _setting_section(settings, "download", "下载")
            if "workers" in download:
                cfg["download"]["workers"] = _setting_int(download["workers"], 1, 32, "下载并发数")
            if "dir" in download:
                text = str(download["dir"]).strip()
                if not text:
                    raise ValueError("下载目录不能为空")
                path = _resolve_download_dir(text)
                try:
                    path.mkdir(parents=True, exist_ok=True)   # 当场建一下，路径错了立刻能说清
                except OSError as e:
                    raise ValueError(f"下载目录建不出来（{path}）：{e}") from None
                cfg["download"]["dir"] = text
            if "retries" in download:
                cfg["download"]["retries"] = _setting_int(
                    download["retries"], 0, 10, "下载重试次数")
            if "auto_resume" in download:
                cfg["download"]["auto_resume"] = bool(download["auto_resume"])

            cache = _setting_section(settings, "cache", "缓存")
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

            splash = _setting_section(settings, "splash", "开场动画")
            if "enabled" in splash:
                cfg["splash"]["enabled"] = bool(splash["enabled"])
            if "min_ms" in splash:
                cfg["splash"]["min_ms"] = _setting_int(splash["min_ms"], 0, 10000, "闪屏最短时长")
            if "max_ms" in splash:
                cfg["splash"]["max_ms"] = _setting_int(splash["max_ms"], 0, 10000, "闪屏最长时长")
        except (ValueError, TypeError) as e:
            # TypeError 也接住：手改过的 config.yaml 可能让某个字段不是预期形状，
            # 那种异常不该以原始形态直穿到 JS 桥（页面上只会看到一句看不懂的 Python 报错）
            raise RuntimeError(f"保存失败：{e}") from e

        try:
            save_config(cfg)
        except OSError as e:
            raise RuntimeError(f"保存失败：config.yaml 写不进去（{e}）") from e
        return cfg
