from __future__ import annotations

import logging
import time

from paper_wiki.web.services.job_manager import JobManager


def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was not met before timeout")


def test_job_progress_reflects_translated_business_logs() -> None:
    manager = JobManager()
    logger = logging.getLogger("paper_wiki.ingestion.pipeline")

    def task() -> dict[str, str]:
        logger.info("步骤 1/3：生成 summary.md")
        time.sleep(0.05)
        logger.info("Layer1 语义产物生成完成：slug=demo")
        return {"slug": "demo"}

    job = manager.submit(slug="demo", target="ingest", task=task)
    _wait_for(lambda: manager.get(job.job_id).status == "succeeded")

    final = manager.get(job.job_id)
    assert final.progress == "✅ 生成完成"
    assert final.result == {"slug": "demo"}


def test_job_progress_does_not_leak_unrelated_thread_logs() -> None:
    manager = JobManager()
    logger = logging.getLogger("paper_wiki.discovery.recommend")

    def slow_task() -> None:
        time.sleep(0.15)

    job = manager.submit(slug="_recommendations", target="recommend_refresh", task=slow_task)
    # Logged from the test thread, not the job's worker thread: must not be captured.
    logger.info("开始生成每日推荐")
    _wait_for(lambda: manager.get(job.job_id).status == "succeeded")

    assert manager.get(job.job_id).progress is None


def test_job_progress_falls_back_for_unrecognized_log_text() -> None:
    manager = JobManager()
    logger = logging.getLogger("paper_wiki.web.services.candidate_summary")

    def task() -> None:
        logger.info("some log line that isn't in the translation table")

    job = manager.submit(slug="_recommendations", target="recommend_refresh", task=task)
    _wait_for(lambda: manager.get(job.job_id).status == "succeeded")

    assert manager.get(job.job_id).progress == "⚙️ 处理中..."
