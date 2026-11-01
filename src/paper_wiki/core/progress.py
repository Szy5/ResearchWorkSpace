"""Structured step progress for long-running tasks.

Domain code (publishing, ingestion helpers) reports coarse steps through the
module-level helpers here. When the code runs inside a web background job, the
JobManager installs a sink for the current thread and the steps show up in the
job record; anywhere else (CLI, tests) the helpers are silent no-ops.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StepSpec:
    key: str
    label: str
    external: str | None = None


class ProgressSink(Protocol):
    def plan(self, steps: Sequence[StepSpec]) -> None: ...

    def start(self, key: str, *, label: str | None = None, external: str | None = None) -> None: ...

    def detail(self, text: str) -> None: ...

    def finish(self, key: str, *, status: str = "succeeded", detail: str | None = None) -> None: ...


_current_sink: ContextVar[ProgressSink | None] = ContextVar("paper_wiki_progress_sink", default=None)


def install_sink(sink: ProgressSink | None) -> object:
    return _current_sink.set(sink)


def reset_sink(token: object) -> None:
    _current_sink.reset(token)  # type: ignore[arg-type]


def plan(steps: Sequence[StepSpec]) -> None:
    sink = _current_sink.get()
    if sink is not None:
        sink.plan(steps)


def detail(text: str) -> None:
    sink = _current_sink.get()
    if sink is not None:
        sink.detail(text)


def skip(key: str, reason: str | None = None) -> None:
    sink = _current_sink.get()
    if sink is not None:
        sink.finish(key, status="skipped", detail=reason)


@contextmanager
def step(key: str, label: str | None = None, *, external: str | None = None) -> Iterator[None]:
    sink = _current_sink.get()
    if sink is None:
        yield
        return
    sink.start(key, label=label, external=external)
    try:
        yield
    except BaseException as exc:
        sink.finish(key, status="failed", detail=str(exc) or type(exc).__name__)
        raise
    sink.finish(key)
