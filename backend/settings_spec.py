"""
设置项的**唯一出处**：标签、范围、枚举值、提示、要不要重启，全写在这儿。

为什么要有这么一张表：以前每加一个配置项都得改五个地方（`config.py` 的默认值、`config.yaml`、
`frontend/src/settings.ts`、`pages/settings.ts` 的字段表、`save_settings` 里那段逐键 `if`），
漏一处就是"设置页存不下去"或者"改了不生效"。现在：

  * `save_settings` 按这张表逐项校验（不再有 if 链）；
  * `get_settings_spec()` 把这张表原样给前端，**设置页的表单也是它生成的** ——
    加一个配置项 = `config.py` 的 DEFAULT_CONFIG 里加一行 + 在这儿加一行（标签 / 范围）。

段的 key 与 `DEFAULT_CONFIG` 的段一一对应（不做点号路径那种"一个字段跨两段"的事，
省得保存时还要打补丁）；字段的 key 就是段里的键名。

kind 决定控件与校验：
  text 文本框 / int 数字 / float 小数 / bool 开关 / enum 下拉 / int_pair 两个数字 /
  dir 目录（会当场建出来）/ url 地址
"""
from typing import Any

from backend.paths import resolve_download_dir

SECTIONS: list[dict[str, Any]] = [
    {
        "key": "window",
        "label": "窗口",
        "fields": [
            {"key": "title", "label": "窗口标题", "kind": "text", "required": True, "restart": True},
            {"key": "width", "label": "窗口宽度", "kind": "int", "min": 400, "max": 5000, "restart": True},
            {"key": "height", "label": "窗口高度", "kind": "int", "min": 400, "max": 5000, "restart": True},
            {"key": "min_size", "label": "最小窗口尺寸（宽、高）", "kind": "int_pair", "min": 200, "max": 5000,
             "restart": True},
            {"key": "glass", "label": "窗口毛玻璃", "kind": "enum",
             "options": ["none", "mica", "acrylic", "tabbed"],
             "hint": "acrylic 最像毛玻璃；Win11 22H2 起才有效", "restart": True},
            {"key": "glass_opacity", "label": "窗口不透明度", "kind": "float", "min": 0.35, "max": 1,
             "step": 0.01, "hint": "1 = 完全不透明；0.9 左右又透又看得清字", "restart": True},
            {"key": "remember_geometry", "label": "记住窗口位置与大小", "kind": "bool",
             "hint": "关窗那一刻记下来，下次开窗照上次的摆", "restart": True},
        ],
    },
    {
        "key": "dev",
        "label": "启动（开发）",
        "fields": [
            {"key": "use_dev_server", "label": "用 vite 开发服务器", "kind": "bool",
             "hint": "开发用：连着 vite（5173）改前端不用重打包。打包后的包没有 vite，关着就行 —— 关了是加载包内 dist",
             "restart": True},
            {"key": "url", "label": "启动地址", "kind": "url",
             "hint": "只在上面那项打开时才会去连它；打包后的包不走这里", "restart": True},
            {"key": "debug", "label": "调试模式", "kind": "bool", "hint": "打开后可以用 F12 / 右键检查", "restart": True},
        ],
    },
    {
        "key": "server",
        "label": "本地服务",
        "fields": [
            {"key": "port", "label": "本地服务端口", "kind": "int", "min": 1024, "max": 65535,
             "hint": "页面与图片走同一个端口（同源）：被占就顺着往下退 7 个，还不行就用系统随机端口；"
                     "但换了端口，主题 / 偏好那一份 localStorage 也跟着换（等于重置）", "restart": True},
        ],
    },
    {
        "key": "splash",
        "label": "开场动画",
        "fields": [
            {"key": "enabled", "label": "开场动画", "kind": "bool",
             "hint": "开窗先播「GuZhu」描字动画，放完飞进左上角；动画期间后台把首页那批数据先拉起来",
             "restart": True},
            {"key": "min_ms", "label": "最短时长（毫秒）", "kind": "int", "min": 0, "max": 10000,
             "hint": "从页面开始加载算起", "restart": True},
            {"key": "max_ms", "label": "最长时长（毫秒）", "kind": "int", "min": 0, "max": 10000,
             "hint": "硬上限：数据再慢也到点就揭幕，露出的骨架后面自己补上", "restart": True},
        ],
    },
    {
        "key": "reader",
        "label": "阅读器",
        "fields": [
            {"key": "restore_progress", "label": "自动回到上次那一页", "kind": "bool"},
            {"key": "click_to_page", "label": "点击左右两侧翻页", "kind": "bool", "hint": "关掉后只能滚轮 / 方向键翻页"},
            {"key": "mode", "label": "阅读模式", "kind": "enum", "options": ["webtoon", "single"],
             "hint": "webtoon = 连续滚动，single = 单页翻页（阅读器里改是立即生效）"},
            {"key": "background", "label": "背景色", "kind": "enum", "options": ["dark", "black", "gray", "light"]},
            {"key": "page_gap", "label": "页间距（像素）", "kind": "int", "min": 0, "max": 64,
             "hint": "只在连续滚动模式有效"},
            {"key": "width", "label": "阅读器图片宽度（像素）", "kind": "int", "min": 0, "max": 2400,
             "hint": "漫画列最多这么宽，0 = 铺满窗口；进阅读器时生效"},
            {"key": "auto_scroll", "label": "自动滚屏速度（像素/秒）", "kind": "int", "min": 0, "max": 1000,
             "hint": "0 = 关；只在连续滚动模式有效"},
        ],
    },
    {
        "key": "detail",
        "label": "详情页",
        "fields": [
            {"key": "chapters_collapse", "label": "章节超过几话就折叠", "kind": "int", "min": 0, "max": 500,
             "hint": "0 = 全部展开；折叠后还能一键展开，或直接跳到上次读到的那话"},
            {"key": "comment_preview", "label": "评论区展开后先显示几条", "kind": "int", "min": 0, "max": 50,
             "hint": "0 = 不显示评论区；评论只读，不需要登录"},
        ],
    },
    {
        "key": "prefetch",
        "label": "预加载",
        "fields": [
            {"key": "albums", "label": "列表铺完后预热几部的详情", "kind": "int", "min": 0, "max": 30,
             "hint": "后台一批最多预热这么多部的详情（0 = 关）", "restart": True},
            {"key": "chapter_images", "label": "进详情 / 翻页时先下几张图", "kind": "int", "min": 0, "max": 20,
             "hint": "0 = 关", "restart": True},
            {"key": "next_at", "label": "看到多少比例就预加载下一话", "kind": "float", "min": 0, "max": 1,
             "step": 0.05, "hint": "0 = 关", "restart": True},
        ],
    },
    {
        "key": "recommend",
        "label": "推荐",
        "fields": [
            {"key": "limit", "label": "一次铺几张推荐卡片", "kind": "int", "min": 0, "max": 50,
             "hint": "0 = 关掉推荐那段", "restart": True},
            {"key": "candidates", "label": "候选池大小", "kind": "int", "min": 5, "max": 200,
             "hint": "热度榜前 N 部当候选", "restart": True},
            {"key": "hot_weight", "label": "热度先验的占比", "kind": "float", "min": 0, "max": 1, "step": 0.05,
             "hint": "0 = 纯画像，1 = 纯热度", "restart": True},
            {"key": "author_boost", "label": "作者命中的加成倍数", "kind": "float", "min": 0, "max": 5,
             "step": 0.1, "restart": True},
            {"key": "half_life_days", "label": "画像半衰期（天）", "kind": "int", "min": 1, "max": 365,
             "restart": True},
        ],
    },
    {
        "key": "download",
        "label": "下载",
        "fields": [
            {"key": "workers", "label": "图片下载并发数", "kind": "int", "min": 1, "max": 32,
             "hint": "太大容易被图源限速", "restart": True},
            {"key": "dir", "label": "下载目录", "kind": "dir",
             "hint": "整本下载的离线副本放这儿（用户数据，清缓存不会删）；支持 ~ 与相对路径（相对 ~/.jmreader）",
             "restart": True},
            {"key": "retries", "label": "单张图重试次数", "kind": "int", "min": 0, "max": 10,
             "hint": "还是失败就跳过它，点「继续下载」时再补", "restart": True},
            {"key": "auto_resume", "label": "开窗自动接着下", "kind": "bool",
             "hint": "上次没下完的，开窗几秒后自动续传，只补缺的部分", "restart": True},
        ],
    },
    {
        "key": "cache",
        "label": "缓存",
        "fields": [
            {"key": "photo_ttl", "label": "章节图列表缓存（秒）", "kind": "int", "min": 0, "max": 2592000,
             "restart": True},
            {"key": "album_ttl", "label": "漫画详情缓存（秒）", "kind": "int", "min": 0, "max": 2592000,
             "restart": True},
            {"key": "search_ttl", "label": "搜索缓存（秒）", "kind": "int", "min": 0, "max": 2592000,
             "restart": True},
            {"key": "ranking_ttl", "label": "榜单缓存（秒）", "kind": "int", "min": 0, "max": 2592000,
             "restart": True},
            {"key": "comment_ttl", "label": "评论缓存（秒）", "kind": "int", "min": 0, "max": 2592000,
             "restart": True},
            {"key": "max_size_mb", "label": "缓存上限（MB）", "kind": "int", "min": 0, "max": 102400,
             "hint": "2048 就是 2G，0 = 不限；章节图和接口缓存都算在里面", "restart": True},
            {"key": "cleanup_interval", "label": "定时清理间隔（秒）", "kind": "int", "min": 30, "max": 86400,
             "hint": "后台每隔这么久检查一次，超上限就删最久没看的章节图", "restart": True},
        ],
    },
    {
        "key": "update",
        "label": "更新",
        "fields": [
            {"key": "enabled", "label": "开启更新通道", "kind": "bool",
             "hint": "只热更**前端**（页面与素材）：装完刷新页面就生效，exe 一行都不动，不用重新安装"},
            {"key": "url", "label": "更新地址", "kind": "url",
             "hint": "放 manifest.json 的目录（也可以直接给它 .json 的全路径）；默认指向 code.guzhujushi.cn 上的仓库"},
            {"key": "auto", "label": "开窗后自动查一次", "kind": "bool",
             "hint": "有新版只在页面上提示一句，装不装由你点"},
        ],
    },
    {
        "key": "desktop",
        "label": "桌面集成",
        "fields": [
            {"key": "notify", "label": "系统通知", "kind": "bool",
             "hint": "下载下完 / 出错时弹一条 Windows 通知（右下角）"},
            {"key": "tray", "label": "托盘图标", "kind": "bool",
             "hint": "任务栏右下角放一个图标：右键可以显示窗口、打开数据目录、退出", "restart": True},
            {"key": "autostart", "label": "开机自启", "kind": "bool",
             "hint": "写进当前用户的启动项（注册表 HKCU 的 Run），不碰系统目录、不要管理员权限", "restart": True},
            {"key": "hotkeys", "label": "全局快捷键", "kind": "bool",
             "hint": "窗口不在前台也能用（实验性：注册不上就静默关掉，日志里能查到）", "restart": True},
            {"key": "hotkey_toggle", "label": "显示 / 隐藏窗口的快捷键", "kind": "text",
             "hint": "形如 Ctrl+Alt+G", "restart": True},
        ],
    },
]


def spec_payload() -> dict[str, Any]:
    """给前端的表单定义（原样给，前端按 kind 造控件）"""
    return {"sections": SECTIONS}


def _coerce(field: dict, value: Any) -> Any:
    """按 kind 收口一个字段；不合规就抛 ValueError（消息直接给用户看）"""
    label = field["label"]
    kind = field["kind"]
    if kind == "bool":
        return bool(value)
    if kind in ("int", "float"):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{label}要填数字") from None
        if number != number:                        # NaN
            raise ValueError(f"{label}要填数字")
        lo, hi = field.get("min"), field.get("max")
        if isinstance(lo, (int, float)) and number < lo:
            raise ValueError(f"{label}不能小于 {lo}")
        if isinstance(hi, (int, float)) and number > hi:
            raise ValueError(f"{label}不能大于 {hi}")
        return int(number) if kind == "int" else round(number, 2)
    if kind == "int_pair":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"{label}要填两个数字（宽、高）")
        return [
            _coerce({**field, "kind": "int", "label": f"{label}的{'宽' if i == 0 else '高'}"}, part)
            for i, part in enumerate(value)
        ]
    if kind == "enum":
        text = str(value).strip().lower()
        if text not in field["options"]:
            raise ValueError(f"{label}只能是 {' / '.join(field['options'])}")
        return text
    if kind == "dir":
        text = str(value).strip()
        if not text:
            raise ValueError(f"{label}不能为空")
        path = resolve_download_dir(text)
        try:
            path.mkdir(parents=True, exist_ok=True)     # 当场建一下，路径错了立刻能说清
        except OSError as e:
            raise ValueError(f"{label}建不出来（{path}）：{e}") from None
        return text
    if kind == "url":
        text = str(value).strip()
        if not text.startswith(("http://", "https://", "file://")):
            raise ValueError(f"{label}要以 http:// 或 https:// 或 file:// 开头")
        return text
    text = str(value).strip()
    if field.get("required") and not text:
        raise ValueError(f"{label}不能为空")
    return text


def merge(cfg: dict, submitted: dict) -> dict:
    """
    把设置页交上来的东西并进配置（改的是副本，原 cfg 不动）。

    * 只认表里有的键：表外的键忽略（老前端发来个已经删掉的字段，不该把整次保存拦下来）；
    * 段给了但不是映射（手改过 config.yaml，或者老前端发来 `window: 5`）当场报错说清楚；
    * 数字 / 枚举 / 目录都按 kind 校验，错在哪儿就说哪儿。
    """
    if not isinstance(submitted, dict):
        raise ValueError("设置内容格式不对（应该是一个对象）")
    out = dict(cfg)
    for section in SECTIONS:
        key = section["key"]
        raw = submitted.get(key)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise ValueError(f"{section['label']}那一段要是一个小节（键值对）")
        target = out.get(key)
        if not isinstance(target, dict):
            target = {}
        else:
            target = dict(target)
        for field in section["fields"]:
            name = field["key"]
            if name in raw:
                target[name] = _coerce(field, raw[name])
        out[key] = target
    return out
