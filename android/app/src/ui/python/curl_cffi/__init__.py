"""
x86_64（模拟器）变体专用的 `curl_cffi` 桩。

**为什么需要它**：`curl_cffi` 在 PyPI 上只发布了 `android_24_arm64_v8a` 的安卓轮子，
**没有任何 x86_64 安卓轮子**（`tmp/安卓端技术栈调研.md` §1.5 有逐版本清单）。
而 `jmcomic/jm_async_client.py` 在**模块级**写着 `from curl_cffi.requests import AsyncSession`
—— 没有这个包，`import jmcomic`（进而 `import backend.api`）当场 ModuleNotFoundError。

**它只保证 import 过得去**：任何真正发起请求的调用都会抛 RuntimeError。
也就是说这个变体是拿来看 UI / 壳 / 路由 / 长图渲染的，
**不负责验证「连得上图源」** —— 那是 `full` 变体 + arm64 真机的事。
"""

__version__ = "0.0.0+ui-stub"

_MESSAGE = (
    "curl_cffi 桩（ui 变体）：这个构建里没有真正的 curl_cffi —— "
    "它在 PyPI 上没有 x86_64 的安卓轮子。要看真数据请用 full 变体（arm64 真机）。"
)


class Session:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(_MESSAGE)


class AsyncSession(Session):
    pass


def get(*args, **kwargs):
    raise RuntimeError(_MESSAGE)


def post(*args, **kwargs):
    raise RuntimeError(_MESSAGE)


# jmcomic 走的是 `from curl_cffi.requests import AsyncSession`，所以子模块也要在
from . import requests  # noqa: E402,F401

__all__ = ["requests", "Session", "AsyncSession", "get", "post"]
