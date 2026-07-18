from __future__ import annotations

from fastapi import APIRouter, Depends

from paper_wiki.web.dependencies import get_job_manager
from paper_wiki.web.schemas.job import JobResponse
from paper_wiki.web.services.job_manager import JobManager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, job_manager: JobManager = Depends(get_job_manager)) -> JobResponse:
    return JobResponse.model_validate(job_manager.get(job_id).model_dump())
