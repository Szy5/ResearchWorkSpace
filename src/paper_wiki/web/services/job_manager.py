from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
from threading import Lock
from typing import Any
import uuid

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from paper_wiki.core import progress
from paper_wiki.core.progress import StepSpec
from paper_wiki.web.services.progress_messages import FALLBACK_MESSAGE, step_for_log, translate_progress


class JobStep(BaseModel):
    key: str
    label: str
    status: str = "pending"
    external: str | None = None
    detail: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


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
    steps: list[JobStep] = Field(default_factory=list)


class _ProgressCaptureHandler(logging.Handler):
    """Mirrors the current job's worker-thread INFO logs into JobRecord.progress.

    Business code (IngestPipeline, discovery.recommend, arxiv_source, ...)
    already logs a message at every meaningful step; this handler just listens
    for records emitted on this specific thread while a job runs, translates
    them into user-facing text, and reports them via ``on_message``. Log lines
    that mark a known pipeline stage also advance the job's step list.
    """

    def __init__(
        self,
        thread_ident: int,
        on_message: Callable[[str], None],
        on_step: Callable[[str], None],
    ) -> None:
        super().__init__(level=logging.INFO)
        self._thread_ident = thread_ident
        self._on_message = on_message
        self._on_step = on_step

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self._thread_ident:
            return
        message = record.getMessage()
        step_key = step_for_log(message)
        if step_key:
            self._on_step(step_key)
        self._on_message(translate_progress(message))


class _JobProgressSink:
    """Writes structured step updates for one running job."""

    def __init__(self, manager: "JobManager", job_id: str) -> None:
        self._manager = manager
        self._job_id = job_id

    def plan(self, steps: Sequence[StepSpec]) -> None:
        self._manager._plan_steps(self._job_id, steps)

    def start(self, key: str, *, label: str | None = None, external: str | None = None) -> None:
        self._manager._start_step(self._job_id, key, label=label, external=external)

    def detail(self, text: str) -> None:
        self._manager._step_detail(self._job_id, text)

    def finish(self, key: str, *, status: str = "succeeded", detail: str | None = None) -> None:
        self._manager._finish_step(self._job_id, key, status=status, detail=detail)

    def start_if_planned(self, key: str) -> None:
        self._manager._start_step(self._job_id, key, only_if_planned=True)


class JobNotFoundError(Exception):
    """Raised when a job id is unknown to this process."""


class JobManager:
    """Thread-pool job queue with lightweight filesystem-backed history."""

    def __init__(self, *, max_workers: int = 2, storage_dir: Path | None = None) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="paper-wiki-job")
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._storage_dir = storage_dir
        if self._storage_dir is not None:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_history()
        # Progress capture needs INFO-level business logs to propagate; make sure
        # the paper_wiki namespace allows that even if configure_logging() (which
        # only runs via the `paper-wiki web` CLI entrypoint) never ran in this
        # process, without downgrading an already-more-verbose (DEBUG) setting.
        package_logger = logging.getLogger("paper_wiki")
        if package_logger.getEffectiveLevel() > logging.INFO:
            package_logger.setLevel(logging.INFO)

    def submit(
        self,
        *,
        slug: str,
        target: str,
        task: Callable[[], Any],
        steps: Sequence[StepSpec] | None = None,
    ) -> JobRecord:
        job = JobRecord(
            job_id=uuid.uuid4().hex,
            slug=slug,
            target=target,
            created_at=self._now(),
            steps=[JobStep(key=spec.key, label=spec.label, external=spec.external) for spec in steps or []],
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist_locked(job)
        self._executor.submit(self._run, job.job_id, task)
        return self.get(job.job_id)

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"unknown job id: {job_id}")
            return job.model_copy(deep=True)

    def list(
        self,
        *,
        slug: str | None = None,
        target: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[JobRecord]:
        with self._lock:
            jobs = [job.model_copy(deep=True) for job in self._jobs.values()]
        if slug is not None:
            jobs = [job for job in jobs if job.slug == slug]
        if target is not None:
            jobs = [job for job in jobs if job.target == target]
        if status is not None:
            jobs = [job for job in jobs if job.status == status]
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return jobs[: max(1, min(limit, 500))]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _run(self, job_id: str, task: Callable[[], Any]) -> None:
        self._update(job_id, status="running", started_at=self._now())
        sink = _JobProgressSink(self, job_id)
        handler = _ProgressCaptureHandler(
            threading.get_ident(),
            on_message=lambda text: self._log_progress(job_id, text),
            on_step=sink.start_if_planned,
        )
        root_logger = logging.getLogger("paper_wiki")
        root_logger.addHandler(handler)
        token = progress.install_sink(sink)
        try:
            try:
                result = task()
            except Exception as exc:  # pragma: no cover - exercised through API polling.
                self._close_steps(job_id, failed=True, error=str(exc))
                self._update(job_id, status="failed", finished_at=self._now(), error=str(exc))
                return
        finally:
            progress.reset_sink(token)
            root_logger.removeHandler(handler)
        self._close_steps(job_id, failed=False)
        self._update(job_id, status="succeeded", finished_at=self._now(), result=jsonable_encoder(result))

    def _log_progress(self, job_id: str, text: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            # A generic "processing" line would hide the more specific running step label.
            if text == FALLBACK_MESSAGE and any(item.status == "running" for item in job.steps):
                return
            self._replace_locked(job, progress=text)

    def _plan_steps(self, job_id: str, specs: Sequence[StepSpec]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            known = {item.key for item in job.steps}
            steps = [item.model_copy() for item in job.steps]
            steps.extend(
                JobStep(key=spec.key, label=spec.label, external=spec.external)
                for spec in specs
                if spec.key not in known
            )
            self._replace_locked(job, steps=steps)

    def _start_step(
        self,
        job_id: str,
        key: str,
        *,
        label: str | None = None,
        external: str | None = None,
        only_if_planned: bool = False,
    ) -> None:
        now = self._now()
        with self._lock:
            job = self._jobs[job_id]
            steps = [item.model_copy() for item in job.steps]
            target = next((item for item in steps if item.key == key), None)
            if target is None:
                if only_if_planned:
                    return
                target = JobStep(key=key, label=label or key, external=external)
                steps.append(target)
            if target.status == "running":
                return
            # Steps are sequential: entering a new one closes whatever was still running.
            for item in steps:
                if item.status == "running" and item.key != key:
                    item.status = "succeeded"
                    item.finished_at = now
            target.status = "running"
            target.started_at = now
            target.finished_at = None
            target.detail = None
            if label:
                target.label = label
            if external:
                target.external = external
            self._replace_locked(job, steps=steps, progress=target.label)

    def _step_detail(self, job_id: str, text: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            steps = [item.model_copy() for item in job.steps]
            running = next((item for item in steps if item.status == "running"), None)
            if running is None:
                return
            running.detail = text
            self._replace_locked(job, steps=steps)

    def _finish_step(self, job_id: str, key: str, *, status: str, detail: str | None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            steps = [item.model_copy() for item in job.steps]
            target = next((item for item in steps if item.key == key), None)
            if target is None:
                return
            target.status = status
            target.finished_at = self._now()
            if detail is not None:
                target.detail = detail
            self._replace_locked(job, steps=steps)

    def _close_steps(self, job_id: str, *, failed: bool, error: str | None = None) -> None:
        now = self._now()
        with self._lock:
            job = self._jobs[job_id]
            steps = [item.model_copy() for item in job.steps]
            for item in steps:
                if item.status == "running":
                    item.status = "failed" if failed else "succeeded"
                    item.finished_at = now
                    if failed and error and not item.detail:
                        item.detail = error
                elif item.status == "pending" and not failed:
                    item.status = "skipped"
            self._replace_locked(job, steps=steps)

    def _replace_locked(self, job: JobRecord, **changes: Any) -> None:
        updated = job.model_copy(update=changes)
        self._jobs[job.job_id] = updated
        self._persist_locked(updated)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            self._replace_locked(self._jobs[job_id], **changes)

    def _load_history(self) -> None:
        assert self._storage_dir is not None
        for path in sorted(self._storage_dir.glob("*.json")):
            try:
                job = JobRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logging.getLogger(__name__).warning("跳过不可读取的任务记录：%s, error=%s", path, exc)
                continue
            if job.status in {"pending", "running"}:
                job = job.model_copy(
                    update={
                        "status": "failed",
                        "finished_at": self._now(),
                        "error": "服务进程在任务完成前退出，请重新提交任务。",
                    }
                )
                self._persist_locked(job)
            self._jobs[job.job_id] = job

    def _persist_locked(self, job: JobRecord) -> None:
        if self._storage_dir is None:
            return
        path = self._storage_dir / f"{job.job_id}.json"
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(job.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
