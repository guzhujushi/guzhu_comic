"""config.yaml 的读写；缺失的键用 DEFAULT_CONFIG 补齐。"""
import copy
from typing import Any

import yaml

from backend import paths

# 冻结态落 ~/.jmreader/config.yaml（包可能被放在只读目录），开发态还是仓库根那份
CONFIG_PATH = paths.config_path()

DEFAULT_CONFIG: dict[str, Any] = {
    "window": {
        "title": "Guzhu Comic",
        "width": 1200,
        "height": 800,
        "min_size": [800, 600],
        "glass": "acrylic",   # none / mica / acrylic / tabbed（Win11 22H2+）
        "glass_opacity": 0.92,
    },
    "dev": {
        "url": "http://localhost:5173",
        "use_dev_server": False,   # True = 走 vite 开发服务器（源码态）；打包态没有 vite，只有本地静态服务这条路
        "debug": False,            # 发布默认关；开发机那份 config.yaml 里显式开着
    },
    "server": {
        "port": 47753,             # 前端静态服务端口（页面与图同源）：被占就 47754…47760 依次退让
    },
    "reader": {
        "restore_progress": True,
        "click_to_page": True,
        "mode": "webtoon",
        "background": "dark",
        "page_gap": 0,
        "auto_scroll": 0,
        "width": 1080,
    },
    "detail": {
        "chapters_collapse": 20,   # 章节数超过这个就先折叠（0 = 全部展开）
        "comment_preview": 5,      # 右侧评论区先显示几条（0 = 不显示评论区）
    },
    "prefetch": {
        "albums": 12,           # 列表铺完后后台预热前 N 部的详情缓存（0 = 关）
        "chapter_images": 3,    # 进详情页 / 一话看到 next_at 时先下的图片张数（0 = 关）
        "next_at": 0.9,         # 一话看到这个比例就预加载下一话（0 = 关）
    },
    "recommend": {
        "limit": 10,            # 一次铺几张推荐卡片（0 = 关掉推荐）
        "candidates": 40,       # 候选池大小（热度榜前 N 部）
        "hot_weight": 0.3,      # 打分里热度先验的占比（0 = 纯画像）
        "author_boost": 1.5,    # 作者命中相对 tag 命中的倍数
        "half_life_days": 30,   # 收藏 / 搜索权重的时间半衰期
    },
    "download": {
        "workers": 8,                     # 一话里的并发张数（整本下载与缓存补图共用）
        "dir": "~/.jmreader/downloads",   # 离线副本放哪（用户数据，清缓存不动它）；支持 ~ 与相对路径
        "retries": 3,                     # 单张图失败重试几次（配上下次开窗的续传 = 断线重连）
        "auto_resume": True,              # 开窗几秒后自动接着下没下完的（关窗 / 断电中断的都算）
    },
    "splash": {
        "enabled": True,     # 开窗先播「GuZhu」描字动画（内联在 index.html 里，改完要重开窗口）
        "min_ms": 1950,      # 最早揭幕：从页面开始加载算起（描字 1500 + 停留 450 就是 1950）
        "max_ms": 3000,      # 硬上限：到点必揭，宁可露出骨架也不把启动拖在这
    },
    "cache": {
        "photo_ttl": 86400,
        "album_ttl": 86400,
        "search_ttl": 3600,
        "ranking_ttl": 3600,
        "comment_ttl": 600,
        "max_size_mb": 2048,
        "cleanup_interval": 600,
    },
}


def _merged(base: Any, override: Any) -> Any:
    """逐层合并，override 优先"""
    if isinstance(base, dict) and isinstance(override, dict):
        out = copy.deepcopy(base)
        for key, value in override.items():
            out[key] = _merged(out[key], value) if key in out else copy.deepcopy(value)
        return out
    return copy.deepcopy(base if override is None else override)


class _ConfigDumper(yaml.SafeDumper):
    """映射写块状，一维短列表（min_size）留一行"""
    pass


def _represent_list(dumper: yaml.SafeDumper, data: list) -> yaml.Node:
    flow = all(not isinstance(v, (list, dict)) for v in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_ConfigDumper.add_representer(list, _represent_list)


def load_config() -> dict[str, Any]:
    """
    读 config.yaml，缺的键补默认值。

    这个文件用户能手改，所以每一步都得兜住：读不动、YAML 写坏、顶层不是映射、某一段被写成
    标量 —— 一律退回默认值。开窗路径上就会调用它，抛出去 = 窗口起不来。
    """
    raw: Any = {}
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open(encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            print(f"[config] config.yaml 读不了，先用默认值: {e}", flush=True)
            raw = {}
    cfg = _merged(DEFAULT_CONFIG, raw if isinstance(raw, dict) else {})
    # 某一段被改成标量（比如 `window: 5`）时整段退回默认：不然 cfg["window"]["width"] 当场崩
    for key, default in DEFAULT_CONFIG.items():
        if isinstance(default, dict) and not isinstance(cfg.get(key), dict):
            cfg[key] = copy.deepcopy(default)
    return cfg


def save_config(config: dict[str, Any]) -> None:
    """整份写回 config.yaml：父目录可能还不存在（冻结态首启就是），先建出来"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8", newline="\r\n") as f:
        yaml.dump(config, f, Dumper=_ConfigDumper, allow_unicode=True, sort_keys=False, default_flow_style=False)
