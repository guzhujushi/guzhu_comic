"""config.yaml 的读写；缺失的键用 DEFAULT_CONFIG 补齐。"""
import copy
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

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
        "debug": True,
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
    "download": {
        "workers": 8,
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
    """读 config.yaml，缺的键补默认值"""
    raw: Any = {}
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    return _merged(DEFAULT_CONFIG, raw)


def save_config(config: dict[str, Any]) -> None:
    """整份写回 config.yaml"""
    with CONFIG_PATH.open("w", encoding="utf-8", newline="\r\n") as f:
        yaml.dump(config, f, Dumper=_ConfigDumper, allow_unicode=True, sort_keys=False, default_flow_style=False)
