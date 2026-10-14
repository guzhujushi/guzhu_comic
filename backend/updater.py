"""
前端热更新：查 manifest → 下载 zip → 校验 sha256 → 白名单解压 → 整目录换上去（留一份可回滚）。

**只更新前端**（`~/.jmreader/web/` 覆盖层），exe 一行都不碰 —— 无签名 + 自动下 exe 等于
杀软误报与安全双重坑，那是另一条路（见 `tmp/打包分发设计.md` §8 的「不做自动更新」）。
这里的边界收得很紧，理由写在四个常量的注释里：

  * 只认 https（本机 127.0.0.1 的 http 放行，给回归脚本用）；
  * 解压**只放行页面与素材后缀**，一个可执行后缀都不留 —— 换句话，更新通道被投毒，
    最坏结果也只是"界面被换成别人的"，拿不到命令执行；
  * 单个文件与整包都有体积上限；
  * 装之前先看 index.html 引用的那些 `/assets/...` 在不在（防"传漏了文件"这种自己人事故），
    装之后留一份 web.old；下一次开窗如果这份前端**根本没起来**，自动撤回去（review_boot）。

发布端在 `scripts/publish_frontend.ps1`：算 sha256、写 manifest.json、打 zip，传到
`update.url` 那个地址上去（Gitea 上放两个文件就行，见 manifest.json 的字段说明）。
"""
import hashlib
import io
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from backend import paths
from backend.config import DEFAULT_CONFIG, load_config
from backend.version import APP_VERSION, BUNDLED_WEB

# 更新通道默认地址：Gitea（code.guzhujushi.cn）上一个公开仓库的 web/ 目录，里面放
# manifest.json 与前端 zip。**默认值只写在 config.py 的 DEFAULT_CONFIG 里**（那儿是
# 唯一出处，设置页读的也是它）；仓库还没建的话，在设置页把「更新地址」改成你实际用的那个。
DEFAULT_BASE = str((DEFAULT_CONFIG.get("update") or {}).get("url") or "")
MANIFEST_NAME = "manifest.json"

# 覆盖层的三个兄弟目录
WEB_OLD = paths.APP_DIR / "web.old"      # 上一版（回滚用）
WEB_NEW = paths.APP_DIR / "web.new"      # 解压中转（换上去之前）
BOOT_STATE = paths.APP_DIR / "boot.json"  # 上一次开窗有没有真起来（自动回滚靠它）

# 解压白名单：页面与素材。**别往里加可执行后缀**（.exe/.dll/.bat/.cmd/.ps1/.py/.scr/.msi/.js?）
# —— js 是页面代码，必须在里面；正因为它能在页面里跑，才更要卡死"只有这些"。
ALLOWED_SUFFIXES = frozenset({
    ".html", ".js", ".mjs", ".css", ".json", ".txt", ".map",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf",
})

MAX_ZIP_BYTES = 64 * 1024 * 1024      # 整包上限（正常 300 KB 上下，给足余量）
MAX_ENTRY_BYTES = 16 * 1024 * 1024    # 单个文件上限
MAX_TOTAL_BYTES = 96 * 1024 * 1024    # 解压后总量上限（防 zip bomb 的粗口径）
MAX_MANIFEST_BYTES = 1024 * 1024
BOOT_WATCH_S = 30.0                   # 开窗后多久还没等到前端报到，就当这份前端是坏的


class UpdateError(RuntimeError):
    """更新通道上的任何问题：消息是给人看的（前端直接显示）"""


# ---------------- 版本 / 状态 ----------------

def section() -> dict:
    """config.yaml 的 update 段（读不动就用默认）"""
    cfg = load_config()
    sec = cfg.get("update")
    return sec if isinstance(sec, dict) else {}


def current_web() -> str:
    """
    我这份前端是哪个构建号。

    覆盖层里放着一份 `version.json`（装更新时写进去的）；没有就是 exe 里那份出厂产物
    （`BUNDLED_WEB`，打包脚本写死，空串 = 不知道）。
    """
    marker = paths.WEB_DIR / "version.json"
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            return str((data or {}).get("web") or "")
        except (OSError, ValueError):
            return ""
    return BUNDLED_WEB


def version_info() -> dict:
    """`get_version()` 的返回：关于页 / 设置页显示用"""
    sec = section()
    return {
        "app": APP_VERSION,
        "web": current_web(),
        "built_in": BUNDLED_WEB,
        "frozen": paths.is_frozen(),
        "overlay": paths.WEB_DIR.is_dir(),
        "dist": str(paths.web_dist_dir()),
        "update": {
            "enabled": bool(sec.get("enabled", True)),
            "url": str(sec.get("url") or DEFAULT_BASE),
            "auto": bool(sec.get("auto", True)),
        },
    }


def _ver_tuple(text: Any) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(text or ""))
    return tuple(int(p) for p in parts[:4]) if parts else ()


# ---------------- 网络 ----------------

def _check_url(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        raise UpdateError("更新地址没填（设置页的「更新地址」）")
    parts = urllib.parse.urlsplit(u)
    if parts.scheme == "https" and parts.hostname:
        return u
    if parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost", "::1"):
        return u            # 本机调试（回归脚本起的小服务走这条）
    raise UpdateError("更新地址只能是 https（写成本机 127.0.0.1 的 http 才放行，给调试用）")


def manifest_url(base: str) -> str:
    base = _check_url(base).rstrip("/")
    return base if base.lower().endswith(".json") else f"{base}/{MANIFEST_NAME}"


def _http_get(url: str, timeout: float, limit: int) -> bytes:
    """
    取一个 URL。**先直连、再退回系统 / 环境变量代理**。

    直连优先是有意的：这台机器上 `HTTP_PROXY=127.0.0.1:7890`，而更新服务器是国内可直连的
    （实测 144 ms，证书 Let's Encrypt）——代理一挂、或者未来挪到别的机器上没代理，
    不带这一步就会"明明能连却更新不了"。
    """
    last: Exception | None = None
    openers = (
        urllib.request.build_opener(urllib.request.ProxyHandler({})),   # 直连
        urllib.request.build_opener(),                                   # 环境变量 / 系统代理
    )
    for opener in openers:
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": f"GuzhuComic/{APP_VERSION}",
                "Accept": "*/*",
                "Cache-Control": "no-cache",
            })
            with opener.open(request, timeout=timeout) as resp:
                data = resp.read(limit + 1)
            if len(data) > limit:
                raise UpdateError("更新文件比预期的大，先不装")
            return data
        except UpdateError:
            raise
        except Exception as e:      # noqa: BLE001 —— 网络层的什么错都该退到下一个 opener
            last = e
    raise UpdateError(f"连不上更新地址（{url}）：{last}")


def _parse_manifest(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise UpdateError("更新信息读不懂（不是一份 JSON）") from None
    if not isinstance(data, dict):
        raise UpdateError("更新信息形状不对（应该是一个对象）")
    if not str(data.get("web") or "").strip() or not str(data.get("file") or "").strip():
        raise UpdateError("更新信息里缺 web / file 字段")
    return data


def _load(sec: dict) -> tuple[dict, dict]:
    """取 manifest，回 (检查结果, manifest)"""
    base = str(sec.get("url") or DEFAULT_BASE)
    url = manifest_url(base)
    manifest = _parse_manifest(_http_get(url, 6.0, MAX_MANIFEST_BYTES))
    return url, manifest


def check(sec: dict | None = None) -> dict:
    """
    查一下有没有新版。**失败不抛异常**（开窗 / 打开设置页时顺手调它，不该因此报错刷屏），
    原因都装在 error 里；只有真正要装（apply）时才把错误当错误。
    """
    sec = sec if isinstance(sec, dict) else section()
    out: dict[str, Any] = {
        "enabled": bool(sec.get("enabled", True)),
        "app_version": APP_VERSION,
        "current_web": current_web(),
        "available": False,
        "version": "",
        "web": "",
        "notes": "",
        "size": 0,
        "url": "",
        "app_min": "",
        "too_new": False,
        "known_bad": False,
        "error": "",
    }
    if not out["enabled"]:
        out["error"] = "更新通道关着"
        return out
    try:
        url, manifest = _load(sec)
    except UpdateError as e:
        out["error"] = str(e)
        return out
    except Exception as e:          # noqa: BLE001 —— 兜底：这条路上什么都不该炸到界面上
        out["error"] = f"检查更新失败：{e}"
        return out

    web = str(manifest.get("web")).strip()
    out.update({
        "url": url,
        "web": web,
        "version": str(manifest.get("version") or ""),
        "notes": str(manifest.get("notes") or ""),
        "size": int(manifest.get("size") or 0),
        "app_min": str(manifest.get("app_min") or ""),
    })
    app_min = _ver_tuple(out["app_min"])
    out["too_new"] = bool(app_min and _ver_tuple(APP_VERSION) < app_min)
    out["known_bad"] = web in _bad_builds()
    out["available"] = bool(web) and web != out["current_web"] and not out["too_new"]
    return out


# ---------------- 装 ----------------

def _verify_tree(root: Path) -> None:
    """装之前先看这份产物齐不齐（自己人手抖传漏了文件，就卡在这儿，别换上去）"""
    index = root / "index.html"
    if not index.is_file():
        raise UpdateError("这一版里没有 index.html，先不装")
    try:
        html = index.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise UpdateError(f"index.html 读不了：{e}") from e
    missing = [
        ref for ref in dict.fromkeys(re.findall(r'(?:src|href)="(/[^"]+)"', html))
        if not (root / ref.lstrip("/")).is_file()
    ]
    if missing:
        raise UpdateError("这一版少了文件（发布时传漏了？）：" + "、".join(missing[:3]))


def _extract(raw: bytes, dest: Path) -> int:
    """把 zip 解到 dest；只放行白名单后缀，越界路径当场拒掉"""
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for entry in zf.infolist():
            if entry.is_dir():
                continue
            name = entry.filename.replace("\\", "/")
            if name.startswith("__MACOSX/") or name.rsplit("/", 1)[-1].startswith("."):
                continue                                    # 打包机带出来的垃圾，跳过
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if not parts or ".." in parts:
                raise UpdateError(f"压缩包里有个不安全的路径：{name}")
            if Path(parts[-1]).suffix.lower() not in ALLOWED_SUFFIXES:
                raise UpdateError(f"压缩包里有个不该有的文件：{name}（前端产物只该有页面与素材）")
            if entry.file_size > MAX_ENTRY_BYTES:
                raise UpdateError(f"压缩包里有个特别大的文件：{name}")
            total += entry.file_size
            if total > MAX_TOTAL_BYTES:
                raise UpdateError("压缩包解开来太大，先不装")
            target = dest.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def _swap(new: Path, stamp: dict) -> None:
    """new 换到 WEB_DIR 上；原来那份挪进 WEB_OLD（下次开窗起不来就靠它）"""
    (new / "version.json").write_text(
        json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    if WEB_OLD.exists():
        shutil.rmtree(WEB_OLD, ignore_errors=True)
    if paths.WEB_DIR.exists():
        try:
            paths.WEB_DIR.rename(WEB_OLD)
        except OSError as e:
            raise UpdateError(f"上一个版本的前端挪不动（可能程序还在读它）：{e}") from e
    try:
        new.rename(paths.WEB_DIR)
    except OSError as e:
        if not paths.WEB_DIR.exists() and WEB_OLD.is_dir():
            WEB_OLD.rename(paths.WEB_DIR)          # 换不过去就把老的那份搬回去，别留个空壳
        raise UpdateError(f"替换前端目录失败：{e}") from e


def apply(sec: dict | None = None, force: bool = False) -> dict:
    """
    下载并装上前端更新。返回 `{ok, changed, version, web, files, bytes}`。

    `force=True` 时忽略"这一版上次没起来"那条记录（界面上得先跟用户说清楚）。
    """
    sec = sec if isinstance(sec, dict) else section()
    info = check(sec)
    if info["error"]:
        raise UpdateError(info["error"])
    if info["too_new"]:
        raise UpdateError(
            f"这一版前端要 {info['app_min']} 以上的安装包，现在这版装不了 —— 请去下新版安装包")
    if not info["available"]:
        return {"ok": True, "changed": False, "version": info["version"],
                "web": info["current_web"], "files": 0, "bytes": 0}
    if info["known_bad"] and not force:
        raise UpdateError("这一版上次装上去没能开起来（已经自动退回上一版），先别急着重装")

    _, manifest = _load(sec)
    file = str(manifest.get("file")).strip()
    asset = file if file.startswith(("http://", "https://")) else \
        urllib.parse.urljoin(info["url"], file)
    raw = _http_get(_check_url(asset), 120.0, MAX_ZIP_BYTES)

    size = int(manifest.get("size") or 0)
    if size and len(raw) != size:
        raise UpdateError(f"下载下来的文件大小对不上（{len(raw)} ≠ {size}），先不装")
    sha = str(manifest.get("sha256") or "").strip().lower()
    if sha and hashlib.sha256(raw).hexdigest() != sha:
        raise UpdateError("下载下来的文件校验不过（sha256 对不上），先不装")

    if WEB_NEW.exists():
        shutil.rmtree(WEB_NEW, ignore_errors=True)
    files = _extract(raw, WEB_NEW)
    try:
        _verify_tree(WEB_NEW)
        _swap(WEB_NEW, {
            "web": str(manifest.get("web")),
            "version": str(manifest.get("version") or ""),
            "at": time.time(),
        })
    except Exception:
        shutil.rmtree(WEB_NEW, ignore_errors=True)
        raise
    forget_boot()                       # 新的一份：重新观察它起不起得来（见 mark_boot / review_boot）
    return {"ok": True, "changed": True, "version": str(manifest.get("version") or ""),
            "web": str(manifest.get("web")), "files": files, "bytes": len(raw)}


def rollback() -> dict:
    """手动退回上一版（设置页那个「退回上一版」）"""
    if not WEB_OLD.is_dir():
        raise UpdateError("没有上一版可以退（还没更新过）")
    broken = _spare_name("web.broken")
    if paths.WEB_DIR.exists():
        try:
            paths.WEB_DIR.rename(broken)
        except OSError as e:
            raise UpdateError(f"退不回去：现在这份前端挪不动（{e}）") from e
    try:
        WEB_OLD.rename(paths.WEB_DIR)
    except OSError as e:
        raise UpdateError(f"退不回去：上一版搬不回来（{e}）") from e
    forget_boot()
    return {"ok": True, "web": current_web(), "kept_at": str(broken)}


# ---------------- 起来了没有（自动回滚） ----------------
# 热更新的风险不在"下错文件"（有 sha256 与白名单），而在**新前端本身是坏的**：页面一白，
# 用户连设置页都进不去，只能手删 ~/.jmreader/web。所以留一条自愈的路：
#   mark_boot()   开窗前记一笔「这次用的是哪份前端，还没报到」
#   前端起来后调 notify_booted() 改成「起来了」
#   开窗 30 秒还没报到（watchdog）→ 记成「没起来」
#   下次开窗先看这条记录：写着「没起来」而且覆盖层还是那一份，就自动退回上一版 / 包内那份。

def _spare_name(prefix: str) -> Path:
    """
    给"被换下来的那份前端"起个不撞车的名字。

    原来是 `f"{prefix}-{int(time.time())}"`：同一秒里连着来两次（比如先自动回滚、紧接着用户
    又点了「退回上一版」）就会撞名，rename 直接 FileExistsError。
    """
    base = paths.APP_DIR / f"{prefix}-{int(time.time())}"
    if not base.exists():
        return base
    for i in range(2, 100):
        candidate = base.with_name(f"{base.name}-{i}")
        if not candidate.exists():
            return candidate
    return base.with_name(f"{base.name}-{time.time_ns()}")


def _read_state() -> dict:
    try:
        data = json.loads(BOOT_STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(state: dict) -> None:
    try:
        BOOT_STATE.parent.mkdir(parents=True, exist_ok=True)
        BOOT_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                              encoding="utf-8", newline="\n")
    except OSError as e:
        print(f"[update] 开窗状态写不进去: {e}", flush=True)


def _bad_builds() -> list[str]:
    bad = _read_state().get("bad")
    return [str(x) for x in bad] if isinstance(bad, list) else []


def _remember_bad(web: str) -> None:
    if not web:
        return
    bad = [w for w in _bad_builds() if w != web]
    bad.append(web)
    state = _read_state()
    state["bad"] = bad[-5:]
    _write_state(state)


def forget_boot() -> None:
    """
    清掉"这次起没起来"的观察状态（装完 / 退回后重新开始看）。

    **`bad` 那份名单要留着**：它记的是"哪几版装上去没能开起来"，是这个文件里唯一跨次有效的信息。
    """
    bad = _bad_builds()
    if not bad:
        try:
            BOOT_STATE.unlink(missing_ok=True)
        except OSError:
            pass
        return
    _write_state({"bad": bad})


def mark_boot() -> bool:
    """
    开窗前调用：这次用的是覆盖层吗？是就记一笔「等它报到」。返回是否在用覆盖层。
    """
    if not paths.WEB_DIR.is_dir():
        forget_boot()
        return False
    _write_state({"web": current_web(), "ok": None, "bad": _bad_builds(), "at": time.time()})
    return True


def notify_booted() -> None:
    """前端起来后自己来报到（`main.ts` 里调）；没报到就等着下次被撤掉"""
    state = _read_state()
    if state.get("ok") is None:
        state["ok"] = True
        state["at"] = time.time()
        _write_state(state)


def boot_watchdog() -> None:
    """开窗后盯着：到现在还没报到，就记成「这份前端没起来」"""
    deadline = time.time() + BOOT_WATCH_S
    while time.time() < deadline:
        time.sleep(1.0)
        state = _read_state()
        if state.get("ok") is not None:
            return
    state = _read_state()
    if state.get("ok") is None:
        state["ok"] = False
        state["at"] = time.time()
        _write_state(state)
        print("[update] 开窗 30 秒还没等到前端报到，记一笔（下次开窗会撤掉这份前端）", flush=True)


def review_boot() -> dict:
    """
    开窗**之前**调用：上一次那份前端起来了没有？没起来就撤掉它，保证这次一定能开出来。

    返回 `{rolled_back, note}`：note 非空就是给用户看的一句话（main.py 弹窗 / 打日志）。
    """
    out = {"rolled_back": False, "note": ""}
    state = _read_state()
    if state.get("ok") is not False or not paths.WEB_DIR.is_dir():
        return out
    if str(state.get("web") or "") != current_web():
        return out                     # 覆盖层已经不是记录里那一份了，别误撤
    web_id = str(state.get("web") or "")
    broken = _spare_name("web.broken")
    try:
        paths.WEB_DIR.rename(broken)
    except OSError as e:
        out["note"] = f"上次更新下来的前端没能开起来，但撤不掉它（{e}）：先手动删掉 {paths.WEB_DIR}"
        return out
    _remember_bad(web_id)
    if WEB_OLD.is_dir():
        try:
            WEB_OLD.rename(paths.WEB_DIR)
            out["note"] = "上次更新下来的前端没能开起来，已经自动退回上一版。"
        except OSError as e:
            out["note"] = f"上次那份前端没能开起来，退回上一版也失败了（{e}）：先用包内那份。"
    else:
        out["note"] = "上次更新下来的前端没能开起来，已经自动退回程序自带的那份。"
    out["rolled_back"] = True
    forget_boot()
    print(f"[update] {out['note']}（坏的那份留在 {broken}）", flush=True)
    return out
