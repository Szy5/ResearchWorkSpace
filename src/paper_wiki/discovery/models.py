from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class SearchCandidate(BaseModel):
    """Unified external paper candidate schema."""

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str = ""
    url: str = ""
    venue: str = ""
    arxiv_id: str = ""
    citation_count: int | None = None
    publication_date: date | None = None
    source: str = "arxiv"
    score: float | None = None


class FetchResult(BaseModel):
    """Location information for a fetched paper under raw/{slug}/."""

    slug: str
    raw_dir: Path
    entry_file: str
    has_pdf: bool
    source_file_count: int


class ZoteroCorpusEntry(BaseModel):
    """One Zotero entry used as taste corpus for recommendation reranking."""

    title: str
    abstract: str
    date_added: datetime
    collections: list[str] = Field(default_factory=list)


class RankedCandidate(SearchCandidate):
    """SearchCandidate with recommendation metadata."""

    reason: str = ""
    display_summary: str = ""


class RecommendationSnapshot(BaseModel):
    """Daily recommendation snapshot written to artifacts/.recommendations/."""

    date: date
    generated_at: datetime
    corpus_size: int
    candidate_pool_size: int
    candidates: list[RankedCandidate]
    degraded: bool = False
