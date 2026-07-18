from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
import threading
from threading import Lock
from typing import Any
import uuid

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from paper_wiki.web.services.progress_messages import translate_progress


class JobRecord(BaseModel):
    job_id: str
    slug: str
    target: str
    status: str = "pending"
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    result: Any | None = None
    progress: str | None = None


class _ProgressCaptureHandler(logging.Handler):
    """Mirrors the current job's worker-thread INFO logs into JobRecord.progress.

    Business code (IngestPipeline, discovery.recommend, arxiv_source, ...)
    already logs a message at every meaningful step; this handler just listens
    for records emitted on this specific thread while a job runs, translates
    them into user-facing text, and reports them via ``on_message``. No
    business function signature needs to change.
    """

    def __init__(self, thread_ident: int, on_message: Callable[[str], None]) -> None:
        super().__init__(level=logging.INFO)
        self._thread_ident = thread_ident
        self._on_message = on_message

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self._thread_ident:
            return
        self._on_message(translate_progress(record.getMessage()))


class JobNotFoundError(Exception):
    """Raised when a job id is unknown to this process."""


class JobManager:
    """In-memory v1 job queue backed by a thread pool."""

    def __init__(self, *, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="paper-wiki-job")
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        # Progress capture needs INFO-level business logs to propagate; make sure
        # the paper_wiki namespace allows that even if configure_logging() (which
        # only runs via the `paper-wiki web` CLI entrypoint) never ran in this
        # process, without downgrading an already-more-verbose (DEBUG) setting.
        package_logger = logging.getLogger("paper_wiki")
        if package_logger.getEffectiveLevel() > logging.INFO:
            package_logger.setLevel(logging.INFO)

    def submit(self, *, slug: str, target: str, task: Callable[[], Any]) -> JobRecord:
        job = JobRecord(
            job_id=uuid.uuid4().hex,
            slug=slug,
            target=target,
            created_at=self._now(),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run, job.job_id, task)
        return self.get(job.job_id)

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"unknown job id: {job_id}")
            return job.model_copy(deep=True)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _run(self, job_id: str, task: Callable[[], Any]) -> None:
        self._update(job_id, status="running", started_at=self._now())
        handler = _ProgressCaptureHandler(
            threading.get_ident(),
            on_message=lambda text: self._update(job_id, progress=text),
        )
        root_logger = logging.getLogger("paper_wiki")
        root_logger.addHandler(handler)
        try:
            try:
                result = task()
            except Exception as exc:  # pragma: no cover - exercised through API polling.
                self._update(job_id, status="failed", finished_at=self._now(), error=str(exc))
                return
        finally:
            root_logger.removeHandler(handler)
        self._update(job_id, status="succeeded", finished_at=self._now(), result=jsonable_encoder(result))

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update=changes)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
