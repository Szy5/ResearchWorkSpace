from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from paper_wiki.core.enums import PriorWorkRole
from paper_wiki.graph.artifact_reader import ArtifactReader
from paper_wiki.graph.models import (
    ArtifactBundle,
    DeletePriorWorkRelationEvent,
    GraphEvent,
    GraphPlanResult,
    GraphState,
    PaperNode,
    PriorWorkRelation,
    UpsertPaperEvent,
    UpsertPriorWorkRelationEvent,
)
from paper_wiki.graph.state_store import GraphStateStore


RELATION_TYPE_MAP = {
    PriorWorkRole.BASELINE: "BASELINE",
    PriorWorkRole.INSPIRATION: "INSPIRATION",
    PriorWorkRole.GAP_IDENTIFICATION: "GAP_IDENTIFICATION",
    PriorWorkRole.FOUNDATION: "FOUNDATION",
    PriorWorkRole.EXTENSION: "EXTENSION",
    PriorWorkRole.RELATED_PROBLEM: "RELATED_PROBLEM",
}


class GraphPlanner:
    """把 reviewed artifacts 转成图谱快照和增量事件。"""

    def __init__(self, artifacts_dir: Path, state_dir: Path, updates_dir: Path) -> None:
        self.reader = ArtifactReader(artifacts_dir)
        self.store = GraphStateStore(state_dir, updates_dir)

    def plan_slug(self, slug: str, *, include_unreviewed: bool = False) -> GraphPlanResult:
        bundle = self.reader.load(slug)
        if not include_unreviewed and not bundle.summary.reviewed:
            raise ValueError(f"summary.md is not reviewed: {slug}")

        now = self._now()
        state = self.store.load_state()
        next_state = GraphState.model_validate(state.model_dump(mode="json"))
        paper_nodes, relations = self._build_graph_records(bundle)
        events = self._build_events(slug, bundle.artifact_hash, next_state, paper_nodes, relations, now)
        self.store.save_state(next_state)
        self.store.append_events(events)
        return GraphPlanResult(
            slug=slug,
            events=events,
            paper_keys=[paper.paper_key for paper in paper_nodes],
            relation_keys=[relation.relation_key for relation in relations],
        )

    def _build_graph_records(self, bundle: ArtifactBundle) -> tuple[list[PaperNode], list[PriorWorkRelation]]:
        summary = bundle.summary
        sci_pattern = bundle.sci_pattern
        prior_works = bundle.prior_works
        source_paper_key = build_paper_key(summary.title, summary.year, summary.arxiv_id)

        main_paper = PaperNode(
            slug=summary.slug,
            paper_key=source_paper_key,
            title=summary.title,
            authors=summary.authors,
            year=summary.year,
            venue=summary.venue,
            arxiv_id=summary.arxiv_id,
            primary_pattern_id=sci_pattern.primary_pattern.value,
            primary_pattern_name=sci_pattern.primary_pattern_name,
            secondary_pattern_ids=[pattern.value for pattern in sci_pattern.secondary_patterns],
            secondary_pattern_names=sci_pattern.secondary_pattern_names,
            synthesis_narrative=prior_works.synthesis_narrative,
            sci_pattern_reason=sci_pattern.reasoning,
            is_stub=False,
            added_date=summary.added_date.isoformat(),
        )

        papers: dict[str, PaperNode] = {main_paper.paper_key: main_paper}
        relations: list[PriorWorkRelation] = []

        for entry in prior_works.prior_works:
            target_key = build_paper_key(entry.title, entry.year, entry.arxiv_id)
            papers.setdefault(
                target_key,
                PaperNode(
                    paper_key=target_key,
                    title=entry.title,
                    authors=split_authors(entry.authors),
                    year=entry.year,
                    arxiv_id=entry.arxiv_id,
                    is_stub=True,
                ),
            )
            relation_type = RELATION_TYPE_MAP[entry.role]
            relations.append(
                PriorWorkRelation(
                    relation_key=build_relation_key(source_paper_key, target_key, relation_type),
                    relation_type=relation_type,
                    source_paper_key=source_paper_key,
                    target_paper_key=target_key,
                    source_slug=summary.slug,
                )
            )

        return list(papers.values()), relations

    def _build_events(
        self,
        slug: str,
        artifact_hash: str,
        state: GraphState,
        papers: list[PaperNode],
        relations: list[PriorWorkRelation],
        now: str,
    ) -> list[GraphEvent]:
        events: list[GraphEvent] = []
        for paper in papers:
            existing = state.papers.get(paper.paper_key)
            merged = merge_paper(existing, paper)
            if existing is None or paper_payload(existing) != paper_payload(merged):
                events.append(
                    UpsertPaperEvent(
                        event_id=f"upsert_paper:{paper.paper_key}:{artifact_hash}",
                        paper_key=paper.paper_key,
                        source_slug=slug,
                        artifact_hash=artifact_hash,
                        created_at=now,
                        payload=merged,
                    )
                )
            state.papers[paper.paper_key] = merged

        new_relations = {relation.relation_key: relation for relation in relations}
        for relation in relations:
            existing = state.relations.get(relation.relation_key)
            merged = merge_relation(existing, relation)
            if existing is None or relation_payload(existing) != relation_payload(merged):
                events.append(
                    UpsertPriorWorkRelationEvent(
                        event_id=f"upsert_prior_work_relation:{merged.source_paper_key}:{merged.target_paper_key}:{merged.relation_type}:{artifact_hash}",
                        relation_type=merged.relation_type,
                        source_paper_key=merged.source_paper_key,
                        target_paper_key=merged.target_paper_key,
                        source_slug=slug,
                        artifact_hash=artifact_hash,
                        created_at=now,
                        payload=merged,
                    )
                )
            state.relations[relation.relation_key] = merged

        stale_relation_keys = [
            relation_key
            for relation_key, relation in state.relations.items()
            if relation.source_slug == slug and relation_key not in new_relations
        ]
        for relation_key in stale_relation_keys:
            stale_relation = state.relations.pop(relation_key)
            events.append(
                DeletePriorWorkRelationEvent(
                    event_id=f"delete_prior_work_relation:{stale_relation.source_paper_key}:{stale_relation.target_paper_key}:{stale_relation.relation_type}",
                    relation_type=stale_relation.relation_type,
                    source_paper_key=stale_relation.source_paper_key,
                    target_paper_key=stale_relation.target_paper_key,
                    source_slug=slug,
                    created_at=now,
                )
            )

        return events

    def _now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_paper_key(title: str, year: int | None, arxiv_id: str) -> str:
    normalized_arxiv = arxiv_id.strip().lower()
    if normalized_arxiv:
        return f"arxiv:{normalized_arxiv}"
    normalized_title = normalize_title(title)
    if year is not None:
        return f"title_year:{normalized_title}:{year}"
    digest = hashlib.sha256(normalized_title.encode("utf-8")).hexdigest()[:12]
    return f"title:{digest}"


def build_relation_key(source_paper_key: str, target_paper_key: str, relation_type: str) -> str:
    return f"{source_paper_key}|{relation_type}|{target_paper_key}"


def normalize_title(title: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in title)
    return "-".join(normalized.split())


def split_authors(authors: str) -> list[str]:
    return [author.strip() for author in authors.split(",") if author.strip()]


def merge_paper(existing: PaperNode | None, incoming: PaperNode) -> PaperNode:
    if existing is None:
        return incoming
    merged = existing.model_copy(deep=True)
    incoming_payload = incoming.model_dump(mode="json")
    for key, value in incoming_payload.items():
        if key == "slug" and not value:
            continue
        if key == "authors" and not value:
            continue
        if key in {"title", "venue", "arxiv_id", "primary_pattern_id", "primary_pattern_name", "synthesis_narrative", "sci_pattern_reason"} and not value:
            continue
        if value is None:
            continue
        setattr(merged, key, value)
    if not incoming.is_stub:
        merged.is_stub = False
    return merged


def paper_payload(paper: PaperNode) -> dict:
    return paper.model_dump(mode="json")


def merge_relation(existing: PriorWorkRelation | None, incoming: PriorWorkRelation) -> PriorWorkRelation:
    return incoming if existing is None else incoming


def relation_payload(relation: PriorWorkRelation) -> dict:
    return relation.model_dump(mode="json")
