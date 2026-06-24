from __future__ import annotations

import logging


def configure_logging(verbose: bool = False) -> None:
    """配置 CLI 日志；verbose 模式会输出更细的调试信息和异常堆栈。"""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
