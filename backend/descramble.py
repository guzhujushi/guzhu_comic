"""
整页图「解扰」—— 把图源发来的打乱图还原成正常的一页。

为什么要自己收口这一层（2026-10-15 在安卓上撞见的）：

  * 图源现在发的整页图是**打过乱**的：一页按 jmcomic 的规则切成 num 条横带再倒着重排，
    不解就是一页错位的条带；
  * jmcomic 自己会解（`JmImageTool.decode_and_save`），但那条路**每张图都要 PIL** ——
    `Image.open()` 是当函数实参**先算出来**的，所以连 num==0、根本不用解的图也照样进 PIL；
  * 桌面 Pillow 带 webp 没事；**Chaquopy 的 Pillow 轮子里没有 `PIL/_webp.so`**，
    于是在安卓上每一张图都 `cannot identify image file` → 下载**静默**失败
    （`_download_one` 当时把异常整个吞了，日志里一个字都没有）。

所以这里自己收口：下载时让 jmcomic 只落「原图」（`decode_image=False`，一点不碰 PIL），
再按本模块的规则还原。**横带规则只有这一份实现**，桌面上有跟 jmcomic 逐字节对拍的测试
（`tmp/_check_descramble.py`）；解码器按平台挑：

  * 安卓 → `backend.descramble_android`（系统自带的 BitmapFactory / Canvas，原生支持 webp）
  * 别处 → Pillow（跟 jmcomic 同一条路、同样的编码参数，产物**逐字节相同**）
"""
import importlib

from backend import paths

# 挑好的解码器：第一次真用到才挑，免得 import 期就去碰平台相关的东西
_FIXER = None


def band_plan(height: int, num: int) -> list[tuple[int, int, int]]:
    """
    复刻 jmcomic `JmImageTool.decode_and_save` 的横带规则，返回 [(源起始行, 高度, 目标起始行), ...]。

    口径（`num` 条带、整页高 `height`）：目标第 i 条取自源倒数第 i 条；除不尽的那
    `over = height % num` 行**并进第 0 条**（源与目标都按这个口径对齐，所以第 0 条比别的矮不了）。
    算不出（num<=0 / 尺寸对不上）就返回空表 —— 调用方据此原样放行，别赌。
    """
    if num <= 0 or height <= 0 or num > height:
        return []
    base = height // num
    over = height % num
    plan: list[tuple[int, int, int]] = []
    for i in range(num):
        move = base
        y_src = height - base * (i + 1) - over
        y_dst = base * i
        if i == 0:
            move += over
        else:
            y_dst += over
        if y_src < 0:
            return []
        plan.append((y_src, move, y_dst))
    return plan


def num_for(img) -> int:
    """
    这张图要切成几条 —— 直接问 jmcomic（别自己再实现一遍 `get_num`，免得跟上游漂移）。
    拿不到就返回 0（=不解扰），原样落盘总比落一页切坏的强。

    `.gif` 一律不问：jmcomic 自己也不解 gif（`decide_download_image_decode` 第一句就是它），
    而且动图本来就不是按整页横带切的，硬切只会切坏。
    """
    if str(getattr(img, "img_file_suffix", "") or "").lower() == ".gif":
        return 0
    try:
        from jmcomic import JmImageTool
        return int(JmImageTool.get_num_by_detail(img))
    except Exception:
        return 0


def fix_file(path, num: int) -> None:
    """把 path 上那张打过乱的整页图**就地**还原；num<=0 就什么都不做。"""
    if num > 0:
        _fixer()(path, num)


def _fixer():
    global _FIXER
    if _FIXER is None:
        _FIXER = _pick_fixer()
    return _FIXER


def _pick_fixer():
    """按平台挑解码器；安卓那个走系统自带的（Pillow 在那边没有 webp）"""
    if paths.IS_ANDROID:
        # 动态导入：桌面的 PyInstaller 静态分析不该看见它（里面全是 android.* 的类名）
        return importlib.import_module("backend.descramble_android").fix_file
    return _pil_fix_file


def _pil_fix_file(path, num: int) -> None:
    """
    桌面：Pillow 解码 → 按横带重排 → 存回原路径。

    跟 jmcomic `decode_and_save` 一模一样（`Image.new("RGB")` + `crop`/`paste` + 按后缀存），
    所以产物逐字节相同 —— 这层替掉 jmcomic 之后，桌面上的缓存文件没有任何变化
    （`tmp/_check_descramble.py` 就是拿这个当断言比的）。
    """
    from PIL import Image
    src = Image.open(path)
    src.load()               # 先把像素读进来：下面要往同一个文件覆盖写
    w, h = src.size
    plan = band_plan(h, num)
    if not plan:
        return
    dst = Image.new("RGB", (w, h))
    for y_src, height, y_dst in plan:
        dst.paste(src.crop((0, y_src, w, y_src + height)), (0, y_dst))
    dst.save(path)
