# -*- coding: utf-8 -*-
r"""日志落盘的用例：print / logging / jmcomic 的日志 / 未捕获异常，都得进同一个文件。

跑法：.venv/Scripts/python.exe tmp/_check_logging.py
"""
import importlib
import logging
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import logging_setup, paths  # noqa: E402

FAILS = []


def expect(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        FAILS.append(msg)


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        return "<读不到 %r>" % (e,)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="gz_log_"))
    real_app_dir = paths.APP_DIR
    real_stdout, real_stderr = sys.stdout, sys.stderr

    try:
        paths.APP_DIR = tmp                      # 别往真的 ~/.jmreader 里写
        target = logging_setup.setup()
        expect(target is not None, "setup() 返回了日志路径")
        expect(Path(target).exists(), "日志文件建出来了：%s" % (target,))
        expect((tmp / "logs").is_dir(), "logs 目录在 APP_DIR 下面")

        print("这句是 print 写的", flush=True)
        logging.getLogger("app").info("这句是 logging 写的")
        import jmcomic  # noqa: F401
        from jmcomic.jm_config import jm_logger
        jm_logger.info("这句是 jmcomic 的 logger 写的")
        time.sleep(0.4)          # 等文件 handler 落盘

        text = read(target)
        expect("这句是 print 写的" in text, "print 的内容进了日志文件")
        expect("这句是 logging 写的" in text, "root logging 的内容进了日志文件")
        expect("这句是 jmcomic 的 logger 写的" in text, "jmcomic 的 logger 也顺着 propagate 进了文件")

        # jmcomic 被收编：文件里每条只出现一遍（它自带那个 stdout handler 也往同一个文件写），
        # 没带 topic 的记录不报格式错，带 topic 的 topic 不丢。
        jm_logger.info("这句是 jmcomic 的 logger 写的")            # 第二遍，好数行数
        jm_logger.info("带 topic 的一条", extra={"topic": "api"})
        stray = logging.StreamHandler(sys.stdout)                 # 模拟"先 import 后装日志"的顺序
        jm_logger.addHandler(stray)
        logging_setup._adopt_jmcomic_logger()
        time.sleep(0.4)
        text = read(target)
        expect(text.count("这句是 jmcomic 的 logger 写的") == 2,
               "收编后每条 jm 日志在文件里只出现一遍（实测 %d 遍）" % text.count("这句是 jmcomic 的 logger 写的"))
        expect("jmcomic: 【api】带 topic 的一条" in text, "topic 被折进消息里了")
        expect("Formatting field not found" not in text, "没带 topic 字段也不会报格式错")
        expect(stray not in jm_logger.handlers, "手工塞回去的 stdout handler 会被再次收编")
        expect(jm_logger.handlers, "jmcomic 的 logger 上留了 NullHandler 占位（防它自己再补一个）")

        # 未捕获异常：主线程 hook
        try:
            raise ValueError("主线程炸了")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        # 未捕获异常：线程 hook
        def boom():
            raise RuntimeError("后台线程炸了")

        t = threading.Thread(target=boom, name="boom-thread")
        t.start()
        t.join()
        time.sleep(0.6)
        text = read(target)
        expect("主线程炸了" in text and "Traceback" in text, "主线程未捕获异常连栈进了日志")
        expect("后台线程炸了" in text, "后台线程未捕获异常也进了日志")

        # 重复 setup 不该叠加 handler
        before = len(logging.getLogger().handlers)
        logging_setup.setup()
        expect(len(logging.getLogger().handlers) == before, "重复 setup() 不会重复挂 handler")

        # --windowed 场景：stdout/stderr 是 None 也得能写日志
        sys.stdout = None
        sys.stderr = None
        logging.getLogger("app").warning("stdout 是 None 时也要能写")
        try:
            raise KeyError("None 模式下炸的")
        except KeyError:
            sys.excepthook(*sys.exc_info())
        sys.stdout, sys.stderr = real_stdout, real_stderr
        time.sleep(0.4)
        expect("stdout 是 None 时也要能写" in read(target), "stdout 为 None 时 logging 仍落盘")
        expect("None 模式下炸的" in read(target), "stdout 为 None 时异常仍落盘")

        # 装不上（目录是文件）也要放行
        bad = tmp / "not-a-dir"
        bad.write_text("x", encoding="utf-8")
        paths.APP_DIR = bad
        logging_setup._installed = False
        got = logging_setup.setup()
        expect(got is None, "日志目录建不出来时返回 None（不抛异常）")
    finally:
        sys.stdout, sys.stderr = real_stdout, real_stderr
        paths.APP_DIR = real_app_dir
        logging_setup._installed = False
        for h in list(logging.getLogger().handlers):
            logging.getLogger().removeHandler(h)
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("结果:", FAILS if FAILS else "全部通过", flush=True)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
