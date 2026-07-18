from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from paper_wiki.core.config import Settings
from paper_wiki.discovery import recommend as recommend_service
from paper_wiki.discovery.models import RecommendationSnapshot
from paper_wiki.web.dependencies import get_job_manager, get_settings
from paper_wiki.web.schemas.discovery import RecommendationsRefreshRequest
from paper_wiki.web.schemas.job import JobResponse
from paper_wiki.web.services import candidate_summary
from paper_wiki.web.services.job_manager import JobManager

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

# Recommendation refreshes aren't tied to a single paper, so they use a fixed
# pseudo-slug label when submitted to the shared JobManager.
REFRESH_JOB_SLUG = "_recommendations"


@router.get("/today", response_model=RecommendationSnapshot | None)
def get_today(
    date: Annotated[str | None, Query()] = None,
    settings: Settings = Depends(get_settings),
) -> RecommendationSnapshot | None:
    output_dir = settings.resolved_artifacts_dir() / ".recommendations"
    snapshot_path = output_dir / (f"{date}.json" if date else "latest.json")
    if not snapshot_path.is_file():
        return None
    return RecommendationSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))


@router.post("/refresh", response_model=JobResponse, status_code=202)
def refresh(
    payload: RecommendationsRefreshRequest,
    job_manager: JobManager = Depends(get_job_manager),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    def task() -> dict[str, Any]:
        snapshot = recommend_service.run(
            max_papers=payload.max_papers,
            arxiv_query=payload.arxiv_query,
            settings=settings,
        )
        candidate_summary.enrich_with_display_summary(snapshot, settings)
        return snapshot.model_dump(mode="json")

    job = job_manager.submit(slug=REFRESH_JOB_SLUG, target="recommend_refresh", task=task)
    return JobResponse.model_validate(job.model_dump())
