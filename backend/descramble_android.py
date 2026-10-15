"""
安卓上的解扰解码器：直接用系统自带的 `BitmapFactory` / `Canvas`（走 Chaquopy 的 Java 桥）。

为什么不用 Pillow：Chaquopy 的 Pillow 轮子**没编 webp**（`PIL/_webp.so` 根本不在轮子里），
而图源发的整页图就是 `.webp` —— PIL 连打开都做不到。系统自带的这套（跟 Chromium 同一批底层库）
原生支持 webp，不用额外带任何轮子，也不用装 NDK。

只被 `backend.descramble` 在安卓上 import；桌面别碰这个文件（通篇 android.* 类名）。
"""
from java import jclass

from backend.descramble import band_plan

_Bitmap = jclass("android.graphics.Bitmap")
_BitmapFactory = jclass("android.graphics.BitmapFactory")
_Canvas = jclass("android.graphics.Canvas")
_FileOutputStream = jclass("java.io.FileOutputStream")
_Paint = jclass("android.graphics.Paint")
_Rect = jclass("android.graphics.Rect")

# 重编质量：源图本来就是有损 webp，这里只是解扰后再编一次（桌面那条 Pillow 路用的是默认的 80）
_QUALITY = 90


def fix_file(path, num: int) -> None:
    """把 path 上那张打过乱的整页图就地还原；num<=0 或算不出计划就原样不动。"""
    raw = path.read_bytes()
    src = _BitmapFactory.decodeByteArray(raw, 0, len(raw))
    if src is None:
        raise ValueError("系统解码器认不出这张图（BitmapFactory 返回空）")
    try:
        w, h = int(src.getWidth()), int(src.getHeight())
        plan = band_plan(h, num)
        if not plan:
            return
        dst = _Bitmap.createBitmap(w, h, _Bitmap.Config.ARGB_8888)
        try:
            paint = _Paint()
            paint.setFilterBitmap(False)      # 整条平移，一个像素都不许重采样
            canvas = _Canvas(dst)
            for y_src, height, y_dst in plan:
                canvas.drawBitmap(
                    src,
                    _Rect(0, y_src, w, y_src + height),
                    _Rect(0, y_dst, w, y_dst + height),
                    paint,
                )
            out = _FileOutputStream(str(path))
            try:
                dst.compress(_Bitmap.CompressFormat.WEBP, _QUALITY, out)
            finally:
                out.close()
        finally:
            dst.recycle()
    finally:
        src.recycle()
