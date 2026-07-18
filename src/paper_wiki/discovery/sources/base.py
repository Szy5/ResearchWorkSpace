from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from paper_wiki.discovery.models import SearchCandidate


class SourceAdapter(Protocol):
    def search_by_query(self, query: str, start_year: int, end_year: int, max_results: int) -> list[SearchCandidate]:
        ...


SOURCE_REGISTRY: dict[str, Callable[[], SourceAdapter]] = {}


def get_source(name: str) -> SourceAdapter:
    if name == "arxiv":
        from paper_wiki.discovery.sources import arxiv_source

        return arxiv_source
    raise KeyError(f"Unknown discovery source: {name}")

