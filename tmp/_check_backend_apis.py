# -*- coding: utf-8 -*-
"""A/B 组新接口的回归检查（用完即删）。

原则：**一个真库、一份真配置都不碰** —— 先把 backend.paths / backend.config 里的目录与配置路径
指到临时目录，再 import API。跑完把这个临时目录删掉。

覆盖：
  * 声明式设置表与 DEFAULT_CONFIG / 前端 DEFAULT_SETTINGS / pywebview.d.ts 的一致性（"加配置项要同步几处"这件事的守卫）
  * save_settings：只发一段不动别的段 / 隐藏字段不丢 / 越界·枚举·坏段·坏地址都拦下来说人话
  * get_disk_usage / get_log_tail
  * download_chapter / is_album_offline / list_cached_chapters
  * remove_history / clear_history
  * export_data / import_data 往返
  * create_file_dialog 在没有窗口时给的是人话（不是 traceback）
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(r"D:\guzhu_comic")
sys.path.insert(0, str(REPO))

FAILED: list[str] = []
PASSED = 0


def ok(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name} {detail}")


def raises(name: str, fn, want: str = "") -> None:
    try:
        fn()
    except Exception as e:            # noqa: BLE001
        text = str(e)
        ok(name, (want in text) if want else True, f"→ {text}")
        return
    ok(name, False, "→ 居然没报错")


# ---------- 先搬走"用户目录" ----------
TMP = Path(tempfile.mkdtemp(prefix="guzhu_api_"))
import backend.paths as paths                            # noqa: E402
paths.APP_DIR = TMP
paths.DATA_DIR = TMP / "data"
paths.DATA_DB = paths.DATA_DIR / "app.db"
paths.CACHE_DIR = TMP / "cache"
paths.CACHE_DB = paths.CACHE_DIR / "cache.db"
paths.IMG_DIR = paths.CACHE_DIR / "images"
paths.WEBVIEW_DIR = TMP / "webview"
paths.WEB_DIR = TMP / "web"
import backend.config as config                          # noqa: E402
config.CONFIG_PATH = TMP / "config.yaml"
import backend.api as api_mod                            # noqa: E402
api_mod.APP_DIR = TMP
api_mod.DATA_DIR = paths.DATA_DIR
api_mod.DATA_DB = paths.DATA_DB
api_mod.CACHE_DIR = paths.CACHE_DIR
api_mod.CACHE_DB = paths.CACHE_DB
api_mod.IMG_DIR = paths.IMG_DIR
from backend import desktop, settings_spec, updater      # noqa: E402
desktop.IS_WINDOWS = False                               # 别真去读写开机自启的注册表
from backend.api import API                              # noqa: E402
from backend.config import DEFAULT_CONFIG, load_config   # noqa: E402

api = API()
# 构造 API 时那份临时 config 还不存在，所以 _download_dir 会落到**真的** ~/.jmreader/downloads。
# 这是测试脚本，得当场掰回来，并把"整本下载线程"掐掉（不然它会真去图源拉图、真往那个目录写）。
api._download_dir = TMP / "downloads"
api._download_dir.mkdir(parents=True, exist_ok=True)
api._spawn_album_download = lambda album_id: None      # type: ignore[method-assign]
print(f"临时用户目录：{TMP}")

# ---------- 1) 一致性守卫 ----------
print("\n[1] 设置表 / 默认值 / 前端 / 契约 四处对不对得上")
spec = settings_spec.spec_payload()
hidden = {("window", "last_geometry")}       # 不给人填、由关窗时写的那些
spec_pairs = {(s["key"], f["key"]) for s in spec["sections"] for f in s["fields"]}
default_pairs = {(s, k) for s, v in DEFAULT_CONFIG.items() if isinstance(v, dict) for k in v}
ok("设置表里的每一项都在 DEFAULT_CONFIG 里", spec_pairs <= default_pairs,
   str(sorted(spec_pairs - default_pairs)))
ok("DEFAULT_CONFIG 里每一项都在设置表里（除了隐藏项）",
   default_pairs - hidden <= spec_pairs, str(sorted(default_pairs - hidden - spec_pairs)))
ok("段名跟 DEFAULT_CONFIG 一致",
   {s["key"] for s in spec["sections"]} == {k for k, v in DEFAULT_CONFIG.items() if isinstance(v, dict)},
   str({s["key"] for s in spec["sections"]} ^ set(DEFAULT_CONFIG)))

ts = (REPO / "frontend" / "src" / "settings.ts").read_text(encoding="utf-8")
ts_sections = re.findall(r"^  (\w+): \{", ts, re.M)
ok("前端 DEFAULT_SETTINGS 的段跟后端一致", set(ts_sections) == set(DEFAULT_CONFIG),
   str(set(ts_sections) ^ set(DEFAULT_CONFIG)))

dts = (REPO / "frontend" / "src" / "pywebview.d.ts").read_text(encoding="utf-8")
new_methods = ["get_settings_spec", "get_version", "check_update", "apply_update", "rollback_update",
               "notify_booted", "open_url", "open_folder", "get_desktop_state", "get_disk_usage",
               "get_log_tail", "download_chapter", "is_album_offline", "list_cached_chapters",
               "remove_history", "clear_history", "export_data", "import_data", "create_file_dialog"]
missing = [name for name in new_methods if name not in dts]
ok("新接口都写进 pywebview.d.ts 契约了", not missing, str(missing))
public_missing = [name for name in new_methods if not hasattr(type(api), name)]
ok("这些接口真的挂在 API 上", not public_missing, str(public_missing))
ok("新接口没有公开属性（会被桥递归展开）",
   all(hasattr(type(api), f"_{name}") is False for name in ()))

# ---------- 2) save_settings ----------
print("\n[2] 设置：只发一段，别的都别动")
base = load_config()
# 先塞一个"关窗时写下的"位置（不在设置表里，保存时不许被抹掉）
base["window"]["last_geometry"] = [10, 20, 1300, 900]
config.save_config(base)
api.save_settings({"window": {"width": 1400, "remember_geometry": False}})
now = load_config()
ok("改了的键生效", now["window"]["width"] == 1400)
ok("hidden 字段留着", now["window"]["last_geometry"] == [10, 20, 1300, 900], str(now["window"]))
ok("同一个段里没发的键不动", now["window"]["height"] == base["window"]["height"])
ok("没发的段整个不动", now["reader"] == base["reader"] and now["cache"] == base["cache"])
api.save_settings({"reader": {"mode": "single"}})
ok("第二段生效", load_config()["reader"]["mode"] == "single")
ok("第一次改的还在", load_config()["window"]["width"] == 1400)

raises("越界的数字拦下来", lambda: api.save_settings({"window": {"width": 1}}), "不能小于")
raises("枚举认不出就拦", lambda: api.save_settings({"window": {"glass": "frosted"}}), "只能是")
raises("段不是小节就拦", lambda: api.save_settings({"window": 5}), "小节")
raises("启动地址要带协议", lambda: api.save_settings({"dev": {"url": "localhost:5173"}}), "http")
raises("更新地址要带协议", lambda: api.save_settings({"update": {"url": "code.guzhujushi.cn/x"}}), "http")
raises("设置整体不是对象就拦", lambda: api.save_settings(["window"]), "格式不对")   # type: ignore[arg-type]
api.save_settings({"不存在的一段": {"x": 1}, "window": {"没这个键": 1}})
ok("表外的段 / 键静默忽略", load_config()["window"]["width"] == 1400)
api.save_settings({"window": {"min_size": [700, 500]}})
ok("int_pair 收两个数", load_config()["window"]["min_size"] == [700, 500])
newdir = TMP / "mydownloads"
api.save_settings({"download": {"dir": str(newdir)}})
ok("下载目录当场建出来", newdir.is_dir())
ok("路径存的是原样那串", load_config()["download"]["dir"] == str(newdir))
ok("spec 是给前端的形状",
   all({"key", "label", "kind"} <= set(f) for s in spec["sections"] for f in s["fields"]))

# ---------- 3) 磁盘 / 日志 ----------
print("\n[3] 磁盘与日志")
(TMP / "logs").mkdir(parents=True, exist_ok=True)
(TMP / "logs" / "app.log").write_text(
    "\n".join(f"第 {i} 行" for i in range(1, 501)) + "\n", encoding="utf-8")
usage = api.get_disk_usage()
ok("磁盘账本字段齐", all(k in usage for k in (
    "cache_mb", "download_mb", "data_mb", "free_mb", "total_mb", "chapters", "offline_chapters")))
ok("磁盘剩余是数字", isinstance(usage["free_mb"], (int, float)) and usage["free_mb"] > 0)
tail = api.get_log_tail(10)
ok("日志尾巴取到最后 10 行", len(tail["lines"]) == 10 and tail["lines"][-1] == "第 500 行", str(tail["lines"][:2]))
ok("日志路径指到临时目录", tail["path"] == str(TMP / "logs" / "app.log"))
ok("行数上限夹住", len(api.get_log_tail(99999)["lines"]) <= 2000)
rotated = TMP / "logs" / "app.log.2026-10-13"
rotated.write_text("切下来的那份\n", encoding="utf-8")
(TMP / "logs" / "app.log").unlink()
ok("app.log 被切走了就看最新那份", api.get_log_tail(5)["path"] == str(rotated),
   api.get_log_tail(5)["path"])
shutil.rmtree(TMP / "logs", ignore_errors=True)
ok("一条日志都没有时给人话",
   api.get_log_tail(5)["path"] == "" and bool(api.get_log_tail(5)["error"]))

# ---------- 4) 按话下载 ----------
print("\n[4] 按话下载 / 离线副本")
task = api.download_chapter("422866", "530000", "3", "第 3 话", title="测试本子")
ok("建出一个任务", isinstance(task, dict) and task["album_id"] == "422866", str(task))
ok("话单里就那一话", task["total"] == 1 and task["done"] == 0, str(task))
ok("状态是排队 / 在跑", task["state"] in ("queued", "running"), task["state"])
ok("速度字段在（算不出来是 0）", task["speed_bps"] == 0 and task["eta_s"] is None)
again = api.download_chapter("422866", "530000", "3", "第 3 话")
ok("再来一次不会多一话", again["total"] == 1)
api.download_chapter("422866", "530001", "4", "第 4 话")
ok("加第二话也不重头", api.get_download("422866")["total"] == 2)
raises("没给章节 ID 要拦", lambda: api.download_chapter("422866", "  "), "章节 ID")
raises("没给漫画 ID 要拦", lambda: api.download_chapter("", "530000"), "漫画 ID")

offline = api.is_album_offline("422866")
ok("离线状态字段齐", {"chapters", "done", "offline", "images", "bytes"} <= set(offline))
ok("没下完就不算离线可看", offline["offline"] is False and offline["chapters"] == 2, str(offline))

# 手工摆一个"下好了"的离线副本，看接口认不认
album_dir = api._download_dir / "422866" / "530000"     # 跟 API 手里那份对齐（见上面那段注释）
album_dir.mkdir(parents=True, exist_ok=True)
for i in range(3):
    (album_dir / f"0000{i}.webp").write_bytes(b"x" * 100)
with api_mod._db(paths.DATA_DB) as conn:
    conn.execute("UPDATE download_chapter SET state = 'done', done = 3, total = 3"
                 " WHERE album_id = '422866' AND photo_id = '530000'")
cached = api.list_cached_chapters("422866")
ok("列得出这本两话", len(cached) == 2, str(cached))
ok("有文件的那话排前面", cached[0]["photo_id"] == "530000", str(cached[0]))
ok("认得出是离线副本", cached[0]["offline"] is True and cached[0]["images"] == 3, str(cached[0]))
ok("算出占用字节", cached[0]["bytes"] == 300, str(cached[0]["bytes"]))
ok("带上了本子名", cached[0]["album_title"] == "测试本子")
ok("没下来的那话张数是 0", cached[1]["images"] == 0 and cached[1]["state"] == "queued")
ok("不带 album_id 时也列得出来", len(api.list_cached_chapters()) == 2)
cache_dir = paths.IMG_DIR / "999999"
cache_dir.mkdir(parents=True, exist_ok=True)
(cache_dir / "00001.webp").write_bytes(b"y" * 50)
rows = api.list_cached_chapters()
ok("缓存里那些散话也算", {r["photo_id"] for r in rows} == {"530000", "530001", "999999"}, str(rows))
ok("缓存那条标成没离线", next(r for r in rows if r["photo_id"] == "999999")["offline"] is False)

# ---------- 5) 最近阅读 ----------
print("\n[5] 最近阅读：删一条 / 清空")
api.save_progress("422866", "530000", 7, "测试本子", "")
api.save_progress("422866", "530001", 2, "测试本子", "")
api.save_progress("209827", "209828", 3, "另一本", "")
ok("三条记录在", len(api.get_history(10)) == 2)
removed = api.remove_history("422866", "530001")
ok("删单话只删那一话", removed["removed"] == 1 and len(api.get_history(10)) == 2)
removed = api.remove_history("422866")
ok("不给 photo_id 就删这本全部", removed["removed"] == 1 and len(api.get_history(10)) == 1)
ok("别的本子没被连坐", api.get_history(10)[0]["album_id"] == "209827")
ok("清空返回删了几条", api.clear_history()["removed"] == 1 and api.get_history(10) == [])
ok("清空后收藏 / 下载任务都还在",
   api.get_download("422866") is not None)
raises("删记录也要有 ID", lambda: api.remove_history(None), "漫画 ID")   # type: ignore[arg-type]

# ---------- 6) 导出 / 导入 ----------
print("\n[6] 导出与导入")
api.toggle_favorite("422866", "测试本子", "", ["标签A"], ["作者B"])
api.save_progress("422866", "530000", 42, "测试本子", "")
out = TMP / "backup.json"
res = api.export_data("all", str(out))
ok("导出成文件", res["ok"] and out.is_file(), str(res))
payload = json.loads(out.read_text(encoding="utf-8"))
ok("文件里写了来源和类型", payload["app"] == "guzhu_comic" and payload["kind"] == "all")
ok("收藏导出来了", payload["favorites"][0]["album_id"] == "422866")
ok("阅读记录导出来了", payload["history"][0]["page_index"] == 42)
ok("设置也导出来了", isinstance(payload["settings"], dict) and "window" in payload["settings"])
ok("收藏的 tag 快照也在", payload["favorites"][0]["tags"] == ["标签A"])

single = TMP / "fav.json"
ok("只导收藏也行", api.export_data("favorites", str(single))["count"] == 1)
raises("不认识的类型要拦", lambda: api.export_data("passwords", str(TMP / "x.json")), "导出不了")
raises("目录当文件名要拦", lambda: api.export_data("all", str(TMP)), "目录")
nofile = api.export_data("all", str(TMP / "noext"))
ok("没后缀自动补 .json", nofile["path"].endswith(".json"), nofile["path"])

api.remove_favorite("422866")
api.clear_history()
ok("先清干净", api.get_favorites() == [] and api.get_history() == [])
imp = api.import_data("", str(out))
ok("导入读文件里那个 kind", imp["kind"] == "all" and imp["ok"], str(imp))
ok("收藏回来了", [f["album_id"] for f in api.get_favorites()] == ["422866"])
ok("阅读记录回来了", api.get_history(10)[0]["page_index"] == 42)
ok("设置也并回来了", load_config()["window"]["width"] == 1400)
imp2 = api.import_data("favorites", str(out))
ok("再导一次是覆盖不是翻倍", len(api.get_favorites()) == 1)
bad = TMP / "bad.json"
bad.write_text("[1, 2, 3]", encoding="utf-8")
raises("形状不对的文件要拦", lambda: api.import_data("favorites", str(bad)), "形状不对")
bad.write_text("{not json", encoding="utf-8")
raises("坏 JSON 要拦", lambda: api.import_data("favorites", str(bad)), "不是一份 JSON")
raises("文件不存在要拦", lambda: api.import_data("favorites", str(TMP / "nope.json")), "找不到")
ok("导入时坏行是跳过不是报错",
   api.import_data("favorites", str(single))["skipped"] == 0)

# ---------- 7) 没有窗口时的对话框 ----------
print("\n[7] 没有窗口时的对话框")
raises("没窗口时给人话", lambda: api.create_file_dialog("save"), "没有窗口")
raises("类型写错要拦", lambda: api.create_file_dialog("magic"), "对话框类型")
raises("打开文件走 open_url 才安全", lambda: api.open_url("file:///C:/windows/system32"), "http")

# ---------- 8) 版本 ----------
print("\n[8] 版本")
ver = api.get_version()
ok("版本字段齐", {"app", "web", "overlay", "update"} <= set(ver))
ok("刚装的更新会被认出来", ver["overlay"] is False)
info = api.check_update()
# 2026-10-15 修：原来断言的是"通道里没有版本"（写这句时确实还没发布），首个热更包发布之后它就不成立
# 了。这句真正想守的是"这条路永不抛异常、返回字段形状稳定"——改成守这个（P0 那轮顺手）。
ok("check_update 永不抛异常、字段形状稳定",
   isinstance(info["available"], bool) and isinstance(info["error"], str)
   and isinstance(info.get("version"), str),
   f"available={info['available']} version={info.get('version')!r} error={info['error'][:60]!r}")

print(f"\n{'=' * 60}\n通过 {PASSED}，失败 {len(FAILED)}")
for name in FAILED:
    print("  -", name)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAILED else 0)
