from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from paper_wiki.core.config import Settings
from paper_wiki.core.validation import validate_slug
from paper_wiki.discovery import search as discovery_search
from paper_wiki.ingestion.pipeline import IngestPipeline
from paper_wiki.web.dependencies import get_job_manager, get_paper_repository, get_pipeline_factory, get_settings
from paper_wiki.web.schemas.discovery import BatchIngestRequest, FetchRequest
from paper_wiki.web.schemas.job import JobResponse
from paper_wiki.web.schemas.paper import (
    IngestRequest,
    PaperDetail,
    PaperListItem,
    PaperMetaPatch,
    PriorWorksPatch,
    SummaryPatch,
)
from paper_wiki.web.services.job_manager import JobManager
from paper_wiki.web.services.paper_repository import PaperRepository

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("", response_model=list[PaperListItem])
def list_papers(
    reviewed: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    repository: PaperRepository = Depends(get_paper_repository),
) -> list[PaperListItem]:
    return repository.list_papers(reviewed=reviewed, query=q)


@router.get("/{slug}", response_model=PaperDetail)
def get_paper(slug: str, repository: PaperRepository = Depends(get_paper_repository)) -> PaperDetail:
    return repository.get_paper(validate_slug(slug))


@router.get("/{slug}/files/{relative_path:path}")
def get_artifact_file(
    slug: str,
    relative_path: str,
    repository: PaperRepository = Depends(get_paper_repository),
) -> FileResponse:
    path = repository.resolve_artifact_file(validate_slug(slug), relative_path)
    return FileResponse(path)


@router.patch("/{slug}/meta", response_model=PaperDetail)
def update_meta(
    slug: str,
    payload: PaperMetaPatch,
    repository: PaperRepository = Depends(get_paper_repository),
) -> PaperDetail:
    patch = payload.model_dump(exclude={"expected_updated_at"}, exclude_unset=True)
    return repository.update_meta(validate_slug(slug), patch, expected_updated_at=payload.expected_updated_at)


@router.patch("/{slug}/summary", response_model=PaperDetail)
def update_summary(
    slug: str,
    payload: SummaryPatch,
    repository: PaperRepository = Depends(get_paper_repository),
) -> PaperDetail:
    return repository.update_summary(validate_slug(slug), payload.summary, expected_updated_at=payload.expected_updated_at)


@router.patch("/{slug}/prior-works", response_model=PaperDetail)
def update_prior_works(
    slug: str,
    payload: PriorWorksPatch,
    repository: PaperRepository = Depends(get_paper_repository),
) -> PaperDetail:
    return repository.update_prior_works(
        validate_slug(slug),
        payload.model_dump(exclude={"expected_updated_at"}),
        expected_updated_at=payload.expected_updated_at,
    )


@router.post("/{slug}/ingest", response_model=JobResponse, status_code=202)
def ingest_paper(
    slug: str,
    payload: IngestRequest,
    job_manager: JobManager = Depends(get_job_manager),
    pipeline_factory: Callable[[], IngestPipeline] = Depends(get_pipeline_factory),
) -> JobResponse:
    clean_slug = validate_slug(slug)
    target = ",".join(payload.only or ["summary", "prior_works", "sci_pattern"])
    job = job_manager.submit(
        slug=clean_slug,
        target=target,
        task=_ingest_task(clean_slug, payload, pipeline_factory),
    )
    return JobResponse.model_validate(job.model_dump())


def _ingest_task(
    slug: str,
    payload: IngestRequest,
    pipeline_factory: Callable[[], IngestPipeline],
) -> Callable[[], dict[str, str]]:
    def task() -> dict[str, str]:
        pipeline = pipeline_factory()
        pipeline.run(
            slug,
            overwrite=payload.overwrite,
            summary_prompt=payload.summary_prompt,
            prior_works_prompt=payload.prior_works_prompt,
            sci_pattern_prompt=payload.sci_pattern_prompt,
            only=payload.only,
        )
        return {"slug": slug}

    return task


@router.post("/fetch", response_model=JobResponse, status_code=202)
def fetch_paper(
    payload: FetchRequest,
    job_manager: JobManager = Depends(get_job_manager),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    def task() -> dict[str, Any]:
        result = discovery_search.fetch(
            payload.arxiv_id,
            and_ingest=payload.and_ingest,
            overwrite=payload.overwrite,
            settings=settings,
        )
        return result.model_dump(mode="json")

    job = job_manager.submit(slug=payload.arxiv_id, target="fetch", task=task)
    return JobResponse.model_validate(job.model_dump())


@router.post("/batch-ingest", response_model=list[JobResponse], status_code=202)
def batch_ingest(
    payload: BatchIngestRequest,
    job_manager: JobManager = Depends(get_job_manager),
    pipeline_factory: Callable[[], IngestPipeline] = Depends(get_pipeline_factory),
    settings: Settings = Depends(get_settings),
) -> list[JobResponse]:
    jobs: list[JobResponse] = []
    for item in payload.items:
        if item.slug:
            clean_slug = validate_slug(item.slug)
            ingest_payload = IngestRequest(overwrite=payload.overwrite)
            job = job_manager.submit(
                slug=clean_slug,
                target="ingest",
                task=_ingest_task(clean_slug, ingest_payload, pipeline_factory),
            )
        else:

            def task(arxiv_id: str = item.arxiv_id) -> dict[str, Any]:
                result = discovery_search.fetch(
                    arxiv_id,
                    and_ingest=True,
                    overwrite=payload.overwrite,
                    settings=settings,
                )
                return result.model_dump(mode="json")

            job = job_manager.submit(slug=item.arxiv_id, target="fetch_and_ingest", task=task)
        jobs.append(JobResponse.model_validate(job.model_dump()))
    return jobs
