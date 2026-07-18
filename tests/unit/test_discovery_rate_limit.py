from __future__ import annotations

from pathlib import Path

from paper_wiki.discovery.rate_limit import ArxivThrottle


def test_arxiv_throttle_waits_until_interval(tmp_path: Path) -> None:
    now = 10.0
    sleeps: list[float] = []

    def monotonic() -> float:
        return now + sum(sleeps)

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    throttle = ArxivThrottle(
        0.5,
        state_file=tmp_path / "last.txt",
        monotonic=monotonic,
        sleep=sleep,
    )

    throttle.acquire()
    throttle.acquire()

    assert sleeps == [0.5]

