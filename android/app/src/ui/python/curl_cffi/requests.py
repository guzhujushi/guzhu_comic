"""`curl_cffi.requests` 的替身：把上面的桩原样再导出一遍，够 jmcomic / commonx import。"""

from . import AsyncSession, Session, _MESSAGE, get, post  # noqa: F401

__all__ = ["Session", "AsyncSession", "get", "post"]
