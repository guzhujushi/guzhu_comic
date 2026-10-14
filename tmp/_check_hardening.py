# -*- coding: utf-8 -*-
r"""核对这一轮的健壮性补丁。

全部跑在临时库 / 临时配置 / 假 self 上：不碰真的 data/app.db、cache/cache.db、config.yaml，
也不联网（不实例化 API）。用法：.\.venv\Scripts\python.exe tmp\_check_hardening.py
"""
import json
import sqlite3
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config as cfgmod      # noqa: E402
from backend import api as apimod         # noqa: E402

FAILS = []


def check(name, fn):
    try:
        fn()
        print(f"PASS  {name}")
    except Exception as e:                # noqa: BLE001
        FAILS.append(name)
        print(f"FAIL  {name}: {type(e).__name__}: {e}")


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


tmpdir = Path(tempfile.mkdtemp(prefix="gz_harden_"))
real_config_path = cfgmod.CONFIG_PATH
cfgmod.CONFIG_PATH = tmpdir / "config.yaml"


# ------------------------------------------------------------------ config.yaml 兜底
def broken_yaml():
    cases = {
        "缺失": None,
        "读不了（目录）": "DIR",
        "YAML 写坏": "window: [1, 2\n",
        "顶层是列表": "- 1\n- 2\n",
        "顶层是标量": "5\n",
        "某段是标量": "window: 5\nreader: oops\n",
    }
    import shutil

    for label, text in cases.items():
        p = cfgmod.CONFIG_PATH
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
        if text == "DIR":
            p.mkdir()
        elif text is not None:
            p.write_text(text, encoding="utf-8")
        cfg = cfgmod.load_config()          # 不能抛
        expect(isinstance(cfg, dict), f"{label}: 顶层要是 dict，实际 {type(cfg)}")
        expect(cfg["window"]["width"] == 1200, f"{label}: window.width 应回落默认值")
        expect(cfg["reader"]["mode"] == "webtoon", f"{label}: reader.mode 应回落默认值")
        expect(cfg["cache"]["cleanup_interval"] == 600, f"{label}: cache 段应回落默认值")


check("config.load_config 对坏 config.yaml 一律回默认值", broken_yaml)


# ------------------------------------------------------------------ save_settings
def save_settings_guards():
    fake = types.SimpleNamespace()
    wrote = []
    real_save = apimod.save_config
    apimod.save_config = lambda cfg: wrote.append(cfg)
    try:
        for label, payload in (
            ("window 是数字", {"window": 5}),
            ("reader 是字符串", {"reader": "oops"}),
            ("cache 是列表", {"cache": [1, 2]}),
            ("宽度不是数字", {"window": {"width": "abc"}}),
            ("毛玻璃不认识", {"window": {"glass": "bling"}}),
            ("阅读模式不认识", {"reader": {"mode": "zoom"}}),
            ("无图层的设置体", ["not", "a", "dict"]),
        ):
            try:
                apimod.API.save_settings(fake, payload)      # type: ignore[arg-type]
                raise AssertionError(f"{label}: 应该报错")
            except RuntimeError as e:
                expect("保存失败" in str(e), f"{label}: 错误信息要说人话，实际 {e}")
                expect("Traceback" not in str(e), f"{label}: 不该把原始异常直接透出去")
        expect(wrote == [], "校验没通过就不该写 config.yaml")

        cfg = apimod.API.save_settings(fake, {"reader": {"page_gap": 8}, "window": {"width": 1000}})  # type: ignore[arg-type]
        expect(len(wrote) == 1 and cfg is wrote[0], "合法设置应该恰好写一次")
        expect(cfg["reader"]["page_gap"] == 8 and cfg["window"]["width"] == 1000, "合法设置要落进 cfg")

        apimod.save_config = lambda cfg: (_ for _ in ()).throw(OSError("disk is full"))
        try:
            apimod.API.save_settings(fake, {"reader": {"page_gap": 1}})   # type: ignore[arg-type]
            raise AssertionError("写盘失败应该报错")
        except RuntimeError as e:
            expect("config.yaml" in str(e), f"写盘失败要指明是 config.yaml，实际 {e}")
    finally:
        apimod.save_config = real_save


check("save_settings 非法结构报人话 / 写盘失败可读", save_settings_guards)


# ------------------------------------------------------------------ 临时库
DATA_DB = tmpdir / "app.db"
CACHE_DB = tmpdir / "cache.db"
apimod.DATA_DB = DATA_DB
apimod.CACHE_DB = CACHE_DB

api = apimod.API.__new__(apimod.API)        # 不跑 __init__：不起服务、不联网
api._photo_ttl = 86400
api._client = None

with sqlite3.connect(DATA_DB) as conn:
    conn.execute("CREATE TABLE history (album_id TEXT NOT NULL, photo_id TEXT NOT NULL,"
                 " page_index INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL DEFAULT '',"
                 " cover_url TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL,"
                 " PRIMARY KEY (album_id, photo_id))")
with sqlite3.connect(CACHE_DB) as conn:
    conn.execute("CREATE TABLE meta_cache (key TEXT PRIMARY KEY, data_json TEXT NOT NULL,"
                 " fetched_at REAL NOT NULL)")


# ------------------------------------------------------------------ 缓存形状
def cache_shape():
    apimod.API._cache_set(api, "photo:good", ["1.jpg", "2.jpg"])
    expect(apimod.API._cache_list(api, "photo:good", 86400) == ["1.jpg", "2.jpg"], "正常列表要读得出来")

    apimod.API._cache_set(api, "photo:dict", {"a": 1})
    expect(apimod.API._cache_list(api, "photo:dict", 86400) is None, "dict 形状应判成没命中（_cache_list）")

    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute("INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at) VALUES (?,?,?)",
                     ("photo:bad-json", "{oops", 1e12))
        conn.execute("INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at) VALUES (?,?,?)",
                     ("photo:bad-time", "[1]", "not-a-number"))
        conn.execute("INSERT OR REPLACE INTO meta_cache (key, data_json, fetched_at) VALUES (?,?,?)",
                     ("photo:stale", "[1]", 0))
    expect(apimod.API._cache_get(api, "photo:bad-json", 86400) is None, "JSON 坏掉应判成没命中")
    expect(apimod.API._cache_get(api, "photo:bad-time", 86400) is None, "fetched_at 不是数字应判成没命中")
    expect(apimod.API._cache_get(api, "photo:stale", 1) is None, "过期应判成没命中")


check("缓存形状 / 坏内容不再直穿 TypeError", cache_shape)


# ------------------------------------------------------------------ history
def history_guards():
    apimod.API.save_progress(api, "1", "10", 3, "某本子", "/c.jpg")
    expect(apimod.API.get_progress(api, "1", "10") == 3, "正常存读进度")

    apimod.API.save_progress(api, "2", "20", "abc", None, None)     # 脏页码 + None 文本
    expect(apimod.API.get_progress(api, "2", "20") == 0, "脏页码应回落 0")
    with sqlite3.connect(DATA_DB) as conn:
        row = conn.execute("SELECT title, cover_url FROM history WHERE album_id='2'").fetchone()
    expect(row == ("", ""), f"None 文本应落成空串，实际 {row}")

    apimod.API.save_progress(api, "3", "30", -7, "负数", "")
    expect(apimod.API.get_progress(api, "3", "30") == 0, "负页码应夹到 0")

    for bad in (-5, 0, "abc", None, 10 ** 9):
        rows = apimod.API.get_history(api, bad)
        expect(isinstance(rows, list) and 0 <= len(rows) <= 500, f"limit={bad!r} 应被夹住，实际 {len(rows)}")
    expect(len(apimod.API.get_history(api, 60)) == 3, "正常 limit 应原样生效")


check("save_progress / get_history 归一入参", history_guards)


# ------------------------------------------------------------------ 下载 / 推荐入参
def misc_guards():
    for bad in (5, "oops", {"photo_id": "1"}):
        try:
            apimod.API.start_download(api, "1", "", "", bad)
            raise AssertionError(f"chapters={bad!r} 应该报错")
        except ValueError as e:
            expect("话单" in str(e) or "章节" in str(e), f"错误信息要能看懂，实际 {e}")

    rec = types.SimpleNamespace(_rc_limit=5, _rc_candidates=5, _rc_hot=0.3, _rc_author_boost=1.5,
                               _candidate_pool=lambda: [{"id": "1", "title": "t", "cover_url": ""}],
                               _cached_names=lambda aid: ([], []),
                               _taste_profile=lambda: {"tags": {}, "authors": {}, "favorites": 0, "searches": 0},
                               _rec_reason=lambda *a, **kw: "",
                               _with_favorited=lambda items: items)
    for bad in (5, "oops", {"1": 1}, None):
        out = apimod.API.get_recommendations(rec, "home", 5, bad)
        expect(isinstance(out.get("items"), list), f"exclude={bad!r} 不该把推荐打掉")
    expect(len(apimod.API.get_recommendations(rec, "home", 5, [])["items"]) == 1, "exclude 正常时应有结果")
    expect(len(apimod.API.get_recommendations(rec, "home", 5, ["1"])["items"]) == 0, "exclude 命中的应被剔掉")


def img_name_guards():
    """
    图片文件名收口：`img.filename` 来自图源页面，远端塞路径也不能写到目录外面去。
    """
    class Img:
        def __init__(self, filename, index=1):
            self.filename = filename
            self.index = index

    name = apimod._img_name
    expect(name(Img("00001.webp")) == "00001.webp", "正常的 webp 名字原样返回")
    expect(name(Img("01111.jpg", 5)) == "01111.jpg", "正常的 jpg 名字原样返回")
    expect(name(Img("007.gif")) == "007.gif", "gif 名字原样返回（jmcomic 按后缀选解码）")
    expect(name(Img("a/b/00001.webp")) == "00001.webp", "带目录段的名字只取最后一段")
    expect(name(Img("..\\..\\evil.webp", 7)) == "evil.webp", "反斜杠穿越被砍掉")
    expect(name(Img("../../evil.webp", 7)) == "evil.webp", "正斜杠穿越被砍掉")
    expect(name(Img("a\\b\\..\\..\\x.png", 3)) == "x.png", "混合穿越也只留文件名")
    expect(name(Img("", 9)) == "00009.jpg", "空名字退回序号命名")
    expect(name(Img("..", 4)) == "00004.jpg", "'..' 退回序号命名")
    expect(name(Img("...", 4)) == "00004.jpg", "末尾点是点（Windows 会吃掉）也退回序号")
    expect(name(Img("00001.webp ", 4)) == "00004.webp", "末尾空格退回序号，但后缀保住")
    expect(name(Img("a?b.webp", 6)) == "00006.webp", "带非法字符（?）退回序号")
    expect(name(Img("x.webp\x00", 2)) == "00002.webp", "带控制字符退回序号")
    folder = Path(tempfile.mkdtemp(prefix="gz_name_"))
    for raw in ("..\\..\\evil.webp", "../../evil.webp", "a\\..\\..\\b.png", "...", ".."):
        out = (folder / name(Img(raw, 7))).resolve()
        expect(out.parent == folder.resolve(), "%r 解析后仍在目标目录里（得到 %s）" % (raw, out))


check("图片文件名收口（图源给的名字不许带路径）", img_name_guards)

check("start_download / get_recommendations 入参兜底", misc_guards)

cfgmod.CONFIG_PATH = real_config_path
print()
print("结果:", FAILS if FAILS else "无 —— 全部通过")
sys.exit(1 if FAILS else 0)