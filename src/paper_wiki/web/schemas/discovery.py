from __future__ import annotations

from pydantic import BaseModel, model_validator


class RecommendationsRefreshRequest(BaseModel):
    max_papers: int | None = None
    arxiv_query: str | None = None


class FetchRequest(BaseModel):
    arxiv_id: str
    and_ingest: bool = False
    overwrite: bool = False


class BatchIngestItem(BaseModel):
    """One candidate to turn into a full paper: either a fresh arXiv id or an
    already-fetched local slug (e.g. from a fetch-only /api/papers/fetch call)."""

    arxiv_id: str | None = None
    slug: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "BatchIngestItem":
        if bool(self.arxiv_id) == bool(self.slug):
            raise ValueError("provide exactly one of arxiv_id or slug")
        return self


class BatchIngestRequest(BaseModel):
    items: list[BatchIngestItem]
    overwrite: bool = False
