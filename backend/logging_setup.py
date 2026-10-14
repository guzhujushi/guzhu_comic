"""
把日志落到 ~/.jmreader/logs/。

打包成 `--windowed` 的 exe 之后没有控制台：出问题的时候用户手里什么都没有，只能对着一个不动
的窗口猜，我们也拿不到任何现场。所以开窗第一件事就是装一份日志：

  * `logging` 的 root 记录器 → 文件（jmcomic 那些 `api.xxx` 日志会顺着 propagate 进来）；
  * `sys.stdout` / `sys.stderr` 接一层 Tee → 文件（项目里大量 `print(..., flush=True)` 是给人的
    现场信息，不能因为没控制台就丢掉）；
  * `sys.excepthook` / `threading.excepthook` → 未捕获异常连栈一起落盘（后台线程里炸的最难查）；
  * jmcomic 自带的 stdout handler → 收编（不然每条 jm 日志在文件里重两遍）。

按天切、留 7 天，路径 `~/.jmreader/logs/app.log` —— 用户要反馈问题时，把这个文件发过来就行。

装不上（目录只读 / 磁盘满）只提示一句就放行：日志是辅助，绝不该因为它把窗口拦住。
"""
import logging
import sys
import threading
import traceback
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from backend import paths

FILENAME = "app.log"
BACKUP_DAYS = 7
_LOG_FORMAT = logging.Formatter(
    "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_installed = False
_log_path: Optional[object] = None
_raw_stream = None      # Tee 用的文件句柄，进程活着就开着


class _Tee:
    """
    一份写两处：原来的 stdout/stderr（可能不存在）和日志文件。

    其它属性一律转给原来的流（有些库会摸 `.buffer` / `.fileno()` / `.encoding`），摸不到就让它
    正常抛 AttributeError —— 不要在这儿吞掉别人的预期。
    """

    def __init__(self, stream, raw) -> None:
        self._stream = stream
        self._raw = raw

    def write(self, text):
        if self._stream is not None:
            try:
                self._stream.write(text)
            except Exception:
                pass
        if self._raw is not None:
            try:
                self._raw.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self):
        for target in (self._stream, self._raw):
            if target is not None:
                try:
                    target.flush()
                except Exception:
                    pass

    def isatty(self) -> bool:
        return False

    def __getattr__(self, name):
        stream = object.__getattribute__(self, "_stream")
        if stream is None:
            raise AttributeError(name)
        return getattr(stream, name)


def _excepthook(exc_type, exc, tb) -> None:
    # 走 logging 而不是 print：--windowed 下 stdout 可能是个丢弃流（甚至 None），print 会悄没声地没了
    logging.getLogger("app").error("未捕获的异常：\n%s",
                                  "".join(traceback.format_exception(exc_type, exc, tb)))


def _thread_excepthook(args) -> None:
    if args.exc_type is SystemExit:
        return
    text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    logging.getLogger("app").error("后台线程 %s 里未捕获的异常：\n%s",
                                  args.thread.name if args.thread else "?", text)


class _JmTopicFilter(logging.Filter):
    """
    jmcomic 的 topic 折进消息文本里。

    它自带的 handler 用 `【%(topic)s】` 这种带 topic 字段的格式串，只要有一条记录没带 topic
    就整条格式化失败（`Formatting field not found: 'topic'`，往 stderr 吐一坨）。收编它的日志
    之后不再用那个格式串，就得自己把 topic 拼回去 —— 不然日志里看不出是哪一块在说话。
    """

    def filter(self, record) -> bool:
        topic = getattr(record, "topic", None)
        if topic and isinstance(record.msg, str):
            record.msg = "【%s】%s" % (topic, record.msg)
        return True


def _adopt_jmcomic_logger() -> None:
    """
    把 jmcomic 的 logger 收编到 root 上（也就是收编到这个日志文件里）。

    jmcomic 在 import 时就给自己挂一个 `StreamHandler(sys.stdout)`（`if not jm_logger.handlers`
    才挂）。我们装了 Tee，那条 stdout 也是往同一个文件里写 —— 于是每条 jm 日志在文件里出现两遍，
    一遍是它的格式、一遍是 root 的格式，还多带那串 topic 报错。这里：

      * 摘掉它的 StreamHandler，只留 propagate（用户自己开的 jmcomic 文件日志插件是
        FileHandler，不动）；
      * 放一个 NullHandler 占位，jmcomic 之后再 import 也补不回那个 stdout handler；
      * 挂 `_JmTopicFilter`，topic 不丢。

    setup() 早于 jmcomic 的 import（main.py 第一件事就是装日志），所以正常情况下第二条让那个
    handler 根本不会被建出来；万一先 import 后装日志，上面摘 handler 那一步也照样收编。
    """

    jm = logging.getLogger("jmcomic")
    if not any(isinstance(f, _JmTopicFilter) for f in jm.filters):
        jm.addFilter(_JmTopicFilter())
    for handler in list(jm.handlers):
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            jm.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
    if not jm.handlers:
        jm.addHandler(logging.NullHandler())
    jm.propagate = True


def setup():
    """
    装一次（重复调用直接返回）。返回日志文件路径；装不上返回 None。

    注意：没用模块级常量缓存 APP_DIR，是**每次调用现取** —— 测试会把 paths.APP_DIR 指到临时目录。
    """
    global _installed, _log_path, _raw_stream
    if _installed:
        return _log_path
    _installed = True

    log_dir = paths.APP_DIR / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        target = log_dir / FILENAME
        raw = open(target, "a", encoding="utf-8", buffering=1)
    except OSError as e:
        print(f"[log] 日志装不上（不影响使用）: {e}", flush=True)
        return None

    handler = TimedRotatingFileHandler(target, when="midnight", backupCount=BACKUP_DAYS,
                                       encoding="utf-8", delay=True)
    handler.setFormatter(_LOG_FORMAT)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # 从真终端跑（源码态 / --console）才再加一个控制台 handler：logging 也能当场看见；
    # 双击 exe 时 stdout 不是终端，加了只会多一层没用的写。
    if sys.stdout is not None and getattr(sys.stdout, "isatty", lambda: False)():
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(_LOG_FORMAT)
        root.addHandler(console)

    _raw_stream = raw
    sys.stdout = _Tee(sys.stdout, raw)
    sys.stderr = _Tee(sys.stderr, raw)
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    _adopt_jmcomic_logger()

    _log_path = target
    logging.getLogger("app").info("日志已就绪：%s（按天切，留 %d 天）", target, BACKUP_DAYS)
    return target
