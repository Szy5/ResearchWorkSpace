from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from paper_wiki.core.config import Settings
from paper_wiki.ingestion.pipeline import IngestPipeline
from paper_wiki.web.services.job_manager import JobManager
from paper_wiki.web.services.paper_repository import PaperRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_paper_repository(request: Request) -> PaperRepository:
    return request.app.state.paper_repository


def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def get_pipeline_factory(request: Request) -> Callable[[], IngestPipeline]:
    return request.app.state.pipeline_factory
