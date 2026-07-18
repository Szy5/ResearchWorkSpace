from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from paper_wiki.core.config import Settings
from paper_wiki.discovery import search as discovery_search
from paper_wiki.discovery.models import SearchCandidate
from paper_wiki.web.dependencies import get_settings

router = APIRouter(tags=["search"])


@router.get("/api/search", response_model=list[SearchCandidate])
def search_papers(
    q: Annotated[str, Query(min_length=1)],
    start_year: Annotated[int, Query()] = 2020,
    end_year: Annotated[int, Query()] = 2026,
    max_results: Annotated[int | None, Query()] = None,
    settings: Settings = Depends(get_settings),
) -> list[SearchCandidate]:
    return discovery_search.search(q, start_year, end_year, max_results=max_results, settings=settings)
