"""
本地静态服务：一个端口同时喂前端 dist 与图片，外带 `/api`（本地桥，带 token）。

为什么不用 `file://` 直接开 dist/index.html：`<script type="module">` 要走 CORS 检查，而 file:// 的
origin 是 opaque，会被直接拦掉（要绕就得主动给 WebView2 加 --allow-file-access-from-files）；
localStorage 在 file:// 下也不是稳定 origin，「主题 / 榜单偏好跨次留存」就无从谈起。起个本地服务
就这几十行，还顺带让页面与图**同源**（省一次跨源，WebView2 那层图片缓存也能跨次命中）。

P0（2026-10-15）之后这个服务还要管一件事：`POST /api` —— 页面的全部数据调用走它，不再走
pywebview 的 `js_api`（协议与理由见 backend/bridge.py 开头）。同一次改造给 `/api`、`/images`、
`/downloads` 加上了 token 闸门：后两个是用户自己的东西，实测**同机任何程序都能直接读**
（`tmp/现状与技术栈.md` §2.4），带 token 之后读不到了。**静态文件不设防**（前端资源本来就
不保密，仓库里就有）—— 所以没带 token 的浏览器照样能把页面打开，只是页面会明说"地址少了 token"，
而不是一片空白。
"""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from backend.bridge import (PROTECTED_PREFIXES, RPC_PATH, TOKEN_COOKIE, TOKEN_HEADER,
                            TOKEN_QUERY, token_ok)

# 首选端口：> 4096（普通用户进程就能绑，不用管理员）、< 49152（避开 Windows 动态端口段，
# 否则本进程自己的出站连接可能先随机占到它）。依据见 tmp/打包分发设计.md §5。
DEFAULT_PORT = 47753

# 一次请求体最多收这么多：`save_settings` / `prefetch_albums` 这类都进不到 100 KB；
# 再大就不是我们的页面发的，早点断开比慢慢读进来强
MAX_BODY = 16 * 1024 * 1024


class _QuietHandler(SimpleHTTPRequestHandler):
    """
    去掉 http.server 的请求日志，免得刷屏。

    `extra_roots` 是"前缀 -> 目录"的额外映射：离线下载的图在 cache 之外
    （见 download.dir），不挂在同一个服务上的话阅读器就读不到它。
    翻译路径是唯一能换根的地方，所以在这儿拦一道。
    """
    extra_roots: dict[str, Path] = {}
    # 这次开窗的通行证；None = 不设防（源码态 dev 那条路没有本地服务，也就没有 token）
    token: str | None = None
    # API 的派发器（`backend/bridge.py` 的 make_rpc）。None = 这次没挂 API
    rpc: Callable[[str, list], Any] | None = None
    # HTTP/1.1 = 长连接：一话 200 张图连发时不用每次重新握手（回环上也是实打实的省事）。
    # 代价是**每个响应都必须有 Content-Length**，不然客户端会一直等 —— 静态文件、
    # send_error、下面那个 _json 三条路都给了，别再加第四条不带长度的出口。
    protocol_version = "HTTP/1.1"

    # ---------------- token ----------------

    def _token_from_request(self) -> str | None:
        """
        三个地方按顺序找 token：

          * `X-Guzhu-Token` 头 —— 页面自己 fetch 时用（`<img>` 发不出自定义头，所以还有下一条）；
          * `?t=` —— `<img src>`、手打的地址、分享给别的浏览器时用；
          * cookie `guzhu_token` —— 兜底（现在没人种它，留着是为了以后要在多标签间共享时不用改协议）。
        """
        head = (self.headers.get(TOKEN_HEADER) or "").strip()
        if head:
            return head
        query = urlparse(self.path).query
        if query:
            vals = parse_qs(query).get(TOKEN_QUERY) or []
            if vals:
                return vals[0]
        for part in (self.headers.get("Cookie") or "").split(";"):
            key, _, value = part.strip().partition("=")
            if key == TOKEN_COOKIE:
                return value
        return None

    def _token_ok(self) -> bool:
        return token_ok(self._token_from_request(), self.token)

    def _protected(self) -> bool:
        """只有这两个前缀是"本机私有内容"，静态资源不设防（见模块开头那段）"""
        clean = unquote(urlparse(self.path).path)
        return clean.startswith(PROTECTED_PREFIXES)

    # ---------------- 路径 ----------------

    def translate_path(self, path: str) -> str:
        clean = unquote(urlparse(path).path)
        for prefix, root in self.extra_roots.items():
            if clean.startswith(prefix + "/"):
                # 只认路径片段，'..' 这类一律丢掉：别让人越出根目录
                parts = [p for p in clean[len(prefix) + 1:].split("/") if p not in ("", ".", "..")]
                return str(root.joinpath(*parts))
        return super().translate_path(path)

    def end_headers(self) -> None:
        """
        index.html 绝不许走缓存：它引用的资源名是带 hash 的，老 index 配上新包 = 白屏
        （升过一次级就会碰上）。图和带 hash 的 js/css 照旧交给 WebView2 缓存，省流量也快。
        """
        path = urlparse(self.path).path
        if path in ("", "/") or path.endswith(".html"):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    # Host 只认本机回环（见下面 _host_ok 的注释）
    _ALLOWED_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")

    def _host_ok(self) -> bool:
        """
        Host 头必须是本机回环，否则 403。

        不查这一条的话 "DNS rebinding" 那条路是通的：恶意页面把域名解析到 127.0.0.1，
        浏览器就认为跟它同源，于是能读走 /images、/downloads 里的东西（现在这两处还有 token
        兜底，但一层是一层）。Host 里带端口（127.0.0.1:47753）是正常的，这里只看主机名那一段；
        HTTP/1.0 那种不带 Host 的放行（浏览器不会这么发）。
        """
        raw = (self.headers.get("Host") or "").strip().lower()
        if not raw:
            return True
        host = raw.split("]")[0] + "]" if raw.startswith("[") else raw.rsplit(":", 1)[0]
        return host in self._ALLOWED_HOSTS

    # ---------------- GET / HEAD ----------------

    def do_GET(self):
        if not self._host_ok():
            self.send_error(403, "Forbidden host")
            return
        if self._protected() and not self._token_ok():
            self.send_error(403, "Forbidden token")
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._host_ok():
            self.send_error(403, "Forbidden host")
            return
        if self._protected() and not self._token_ok():
            self.send_error(403, "Forbidden token")
            return
        super().do_HEAD()

    def list_directory(self, path: str):
        """
        目录列表一律不给：这个服务只是给页面取图用的，列目录等于把 cache/images 和离线下载
        目录的结构摊开给本机随便哪个程序看。
        """
        self.send_error(403, "Directory listing is disabled")
        return None

    # ---------------- POST /api ----------------

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ValueError("空请求体")
        if length > MAX_BODY:
            raise ValueError(f"请求体太大：{length} > {MAX_BODY}")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    def do_POST(self):
        if not self._host_ok():
            self.send_error(403, "Forbidden host")
            return
        if urlparse(self.path).path != RPC_PATH:
            self.send_error(404, "Not Found")
            return
        if not self._token_ok():
            # 回一句话，别让页面只能看到一句 HTTP 错误码 —— 这条路径最常见的成因是
            # "用户照着旧地址打了 127.0.0.1:47753，没带 ?t="
            self._json({"__error__": "token 不对：请用启动日志里那条带 ?t= 的地址打开"}, 403)
            return
        if self.rpc is None:
            self._json({"__error__": "这次开窗没挂 API（源码态 dev 走 pywebview 的 js_api）"}, 503)
            return
        try:
            payload = self._read_json()
            result = self.rpc(str(payload.get("name") or ""), list(payload.get("args") or []))
            self._json({"__result__": result})
        except Exception as exc:      # 原样回给页面，跟 pywebview 拒绝调用时的观感对齐
            self._json({"__error__": f"{type(exc).__name__}: {exc}"})

    def log_message(self, *args):
        pass


def start_static_server(dist: Path, extra_roots: dict[str, Path] | None = None,
                        port: int = DEFAULT_PORT, overlay: Path | None = None,
                        token: str | None = None,
                        rpc: Callable[[str, list], Any] | None = None) -> str:
    """
    起服务并返回 base url（形如 http://127.0.0.1:47753）。

    端口首选 47753，被占就往后试到 47760，全被占才退回 0（系统随机）。回退有副作用：
    页面 origin 一变，WebView2 里那个 origin 的 localStorage 就是另一份，用户会觉得
    「主题 / 偏好被重置了」—— 所以换端口这件事要打一行日志，别让它悄没声地发生。

    `overlay` 是前端热更新的覆盖层（`~/.jmreader/web`）：**每个请求**都重挑一次根 ——
    覆盖层里有 index.html 就用它，否则用包内 dist。所以要热更新前端，下完刷新页面就行，
    不用重启窗口（换根这件事发生在进程里，端口 / origin 都不变，localStorage 也就没动）。

    `token`：本次开窗的通行证（`backend/bridge.py` 的 new_token）。给了它，`/api`、`/images`、
    `/downloads` 就要带 token；不给 = 不设防。
    `rpc`：API 的派发器（`bridge.make_rpc(api)`）。**必须在页面把请求发出来之前挂上** ——
    调用方（main.py / android_boot.py）是先建 API 再起服务的，顺序天然对。
    """
    roots = dict(extra_roots or {})

    def _pick_root() -> Path:
        if overlay is not None and (overlay / "index.html").is_file():
            return overlay
        return dist

    class _Handler(_QuietHandler):
        extra_roots = roots

        def translate_path(self, path: str) -> str:
            # 换根只在这一处：SimpleHTTPRequestHandler 每次翻译路径都现读 self.directory
            self.directory = str(_pick_root())
            return super().translate_path(path)

    # 挂成**类属性**：本次开窗这两个是常量，而 handler 是每个请求现造的实例。
    # `rpc` 必须包一层 `staticmethod` —— 函数直接挂类属性就成了**方法**，`self.rpc(...)` 会
    # 把 self 当第一个参数塞进去（实测炸法：`dispatch() takes 2 positional arguments but 3 were given`）
    _Handler.token = token
    _Handler.rpc = staticmethod(rpc) if rpc is not None else None

    handler = partial(_Handler, directory=str(dist))
    for candidate in list(range(port, port + 8)) + [0]:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), handler)
        except OSError:
            continue
        bound = server.server_address[1]
        if bound != port:
            print(f"[server] 端口 {port} 被占，这次用 {bound}"
                  f"（主题 / 偏好是跟 origin 走的，换了端口等于换了一份）", flush=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{bound}"
    raise RuntimeError(f"本地服务起不来：{port}~{port + 7} 都被占，随机端口也没绑上")