from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from paper_wiki.web.dependencies import get_job_manager
from paper_wiki.web.schemas.job import JobResponse
from paper_wiki.web.services.job_manager import JobManager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs(
    slug: Annotated[str | None, Query()] = None,
    target: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    job_manager: JobManager = Depends(get_job_manager),
) -> list[JobResponse]:
    return [
        JobResponse.model_validate(job.model_dump())
        for job in job_manager.list(slug=slug, target=target, status=status, limit=limit)
    ]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, job_manager: JobManager = Depends(get_job_manager)) -> JobResponse:
    return JobResponse.model_validate(job_manager.get(job_id).model_dump())
