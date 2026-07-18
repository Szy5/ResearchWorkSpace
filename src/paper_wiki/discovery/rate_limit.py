from __future__ import annotations

import fcntl
import logging
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class ArxivThrottle:
    """Cross-process arXiv throttle backed by flock and a timestamp file."""

    def __init__(
        self,
        min_interval: float = 4.0,
        *,
        state_file: Path | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.min_interval = min_interval
        self.state_file = state_file or Path("/tmp/paper_wiki_arxiv_last_request.txt")
        self.lock_file = self.state_file.with_suffix(self.state_file.suffix + ".lock")
        self.monotonic = monotonic or time.monotonic
        self.sleep = sleep or time.sleep

    def acquire(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_file.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                last_request = self._read_last_request()
                now = self.monotonic()
                elapsed = now - last_request if last_request is not None else self.min_interval
                wait_seconds = max(0.0, self.min_interval - elapsed)
                if wait_seconds > 0:
                    logger.debug("等待arXiv节流：need_wait=%.1fs", wait_seconds)
                    self.sleep(wait_seconds)
                    now = self.monotonic()
                self.state_file.write_text(f"{now:.9f}", encoding="utf-8")
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read_last_request(self) -> float | None:
        if not self.state_file.exists():
            return None
        try:
            return float(self.state_file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None
