"""
P0：本地 HTTP JSON-RPC 桥（带 token）—— 用来替掉 pywebview 的 `js_api`。

协议（一次请求一个调用；够用，而且拿 curl 就能手查）：

    POST http://127.0.0.1:<port>/api
    X-Guzhu-Token: <token>          （或者 ?t=<token>；cookie guzhu_token=<token> 兜底）
    {"name": "get_ranking", "args": ["day", "all", 1, "views"]}

    200 {"__result__": ...}                （方法返回什么就放什么）
    200 {"__error__": "ValueError: ..."}   （方法里抛了：原样回给页面，跟 pywebview 的拒绝对齐）
    403 {"__error__": "token 不对"}         （没带 token / 带错）

为什么换掉 `js_api`（三条，都不是为了好看）：

  1. **手机上根本没有 pywebview** —— 安卓壳里只有 Python 与 WebView，桥只能走网络；
  2. `js_api` 那套注入有已知坑：启动时**会注两遍**，第二遍重建回调表，正在飞的调用 promise 永不
     settle（来龙去脉见 `frontend/src/webstatus.ts` 开头那段）。走 HTTP 之后这一类问题整类消失；
  3. 顺手堵一个实测到的洞：`127.0.0.1:47753` 上**同机任何程序**都能读 `/images`（缓存图）与
     `/downloads`（离线副本），见 `tmp/安卓版可行性评估.md` §6-T8。带 token 之后读不到了。

token 怎么到页面：URL 上的 `?t=`（壳自己拼；用户想用浏览器开就照抄启动日志里那一行）。
**token 绝不写进任何被服务的文件** —— 所以"别的本机程序去 GET /"只能拿到前端那堆静态资源
（它们本来也不保密，仓库里就有），拿不到 token，也就读不到图与下载。
"""
import hmac
import secrets
from typing import Any, Callable

# 协议里的几个名字，改的话 `frontend/src/bridge.ts` 与 `backend/server.py` 要跟着改
RPC_PATH = "/api"
TOKEN_HEADER = "X-Guzhu-Token"
TOKEN_QUERY = "t"
TOKEN_COOKIE = "guzhu_token"

# `/api` 之外的受保护前缀：这两个是本机私有的内容（用户的缓存图与离线副本）
PROTECTED_PREFIXES = ("/images/", "/downloads/")


def new_token() -> str:
    """每次启动换一把。token 只是"本次开窗的通行证"，不需要跨次记住（也就没有落盘的必要）。"""
    return secrets.token_urlsafe(32)


def token_ok(given: str | None, expected: str | None) -> bool:
    """
    比对 token。`expected` 为空 = 这次不设防（源码态 dev 那条路：没有本地服务，也就没有 token）。

    `compare_digest` 是防时序侧信道的老规矩 —— 回环地址上其实没多大意义，但便宜，顺手。
    """
    if not expected:
        return True
    if not given:
        return False
    return hmac.compare_digest(str(given), str(expected))


def make_rpc(api: Any) -> Callable[[str, list], Any]:
    """
    把 API 对象包成 `(名字, 参数) -> 结果` 的可调用，交给 `backend/server.py` 的 `/api`。

    只放行**公开的可调用属性**（跟 pywebview `get_functions` 同一套口径：下划线开头一律不给）。
    `api.py` 里那套"私有名"的规矩（`_jm` / `_download_dir`）在这条路上同样要守 —— 否则
    `api._jm` 这种会被页面当方法调，而它一调就要连图源。
    """

    def dispatch(name: str, args: list) -> Any:
        if not isinstance(name, str) or not name or name.startswith("_"):
            raise AttributeError(f"没有这个方法：{name}")
        fn = getattr(api, name, None)
        if fn is None or not callable(fn):
            raise AttributeError(f"没有这个方法：{name}")
        return fn(*list(args or []))

    return dispatch