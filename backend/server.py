"""
本地静态服务：一个端口同时喂前端 dist 与图片。

为什么不用 `file://` 直接开 dist/index.html：`<script type="module">` 要走 CORS 检查，而 file:// 的
origin 是 opaque，会被直接拦掉（要绕就得主动给 WebView2 加 --allow-file-access-from-files）；
localStorage 在 file:// 下也不是稳定 origin，「主题 / 榜单偏好跨次留存」就无从谈起。起个本地服务
就这几十行，还顺带让页面与图**同源**（省一次跨源，WebView2 那层图片缓存也能跨次命中）。
"""
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

# 首选端口：> 4096（普通用户进程就能绑，不用管理员）、< 49152（避开 Windows 动态端口段，
# 否则本进程自己的出站连接可能先随机占到它）。依据见 tmp/打包分发设计.md §5。
DEFAULT_PORT = 47753


class _QuietHandler(SimpleHTTPRequestHandler):
    """
    去掉 http.server 的请求日志，免得刷屏。

    `extra_roots` 是"前缀 -> 目录"的额外映射：离线下载的图在 cache 之外
    （见 download.dir），不挂在同一个服务上的话阅读器就读不到它。
    翻译路径是唯一能换根的地方，所以在这儿拦一道。
    """
    extra_roots: dict[str, Path] = {}

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
        浏览器就认为跟它同源，于是能读走 /images、/downloads 里的东西。Host 里带端口
        （127.0.0.1:47753）是正常的，这里只看主机名那一段；HTTP/1.0 那种不带 Host 的
        放行（浏览器不会这么发）。
        """
        raw = (self.headers.get("Host") or "").strip().lower()
        if not raw:
            return True
        host = raw.split("]")[0] + "]" if raw.startswith("[") else raw.rsplit(":", 1)[0]
        return host in self._ALLOWED_HOSTS

    def do_GET(self):
        if not self._host_ok():
            self.send_error(403, "Forbidden host")
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._host_ok():
            self.send_error(403, "Forbidden host")
            return
        super().do_HEAD()

    def list_directory(self, path: str):
        """
        目录列表一律不给：这个服务只是给页面取图用的，列目录等于把 cache/images 和离线下载
        目录的结构摊开给本机随便哪个程序看。
        """
        self.send_error(403, "Directory listing is disabled")
        return None

    def log_message(self, *args):
        pass


def start_static_server(dist: Path, extra_roots: dict[str, Path] | None = None,
                        port: int = DEFAULT_PORT, overlay: Path | None = None) -> str:
    """
    起服务并返回 base url（形如 http://127.0.0.1:47753）。

    端口首选 47753，被占就往后试到 47760，全被占才退回 0（系统随机）。回退有副作用：
    页面 origin 一变，WebView2 里那个 origin 的 localStorage 就是另一份，用户会觉得
    「主题 / 偏好被重置了」—— 所以换端口这件事要打一行日志，别让它悄没声地发生。

    `overlay` 是前端热更新的覆盖层（`~/.jmreader/web`）：**每个请求**都重挑一次根 ——
    覆盖层里有 index.html 就用它，否则用包内 dist。所以要热更新前端，下完刷新页面就行，
    不用重启窗口（换根这件事发生在进程里，端口 / origin 都不变，localStorage 也就没动）。
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
