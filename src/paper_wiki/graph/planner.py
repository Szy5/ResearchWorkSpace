from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from paper_wiki.core.enums import PriorWorkRole
from paper_wiki.graph.artifact_reader import ArtifactReader
from paper_wiki.graph.models import (
    ArtifactBundle,
    AuthorNode,
    AuthorshipRelation,
    DeleteAuthorshipEvent,
    DeletePatternClassificationEvent,
    DeletePriorWorkRelationEvent,
    GraphEvent,
    GraphPlanResult,
    GraphState,
    PaperNode,
    PatternClassificationRelation,
    PatternNode,
    PriorWorkRelation,
    UpsertAuthorEvent,
    UpsertAuthorshipEvent,
    UpsertPaperEvent,
    UpsertPatternClassificationEvent,
    UpsertPatternEvent,
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
        if not include_unreviewed and not (bundle.manifest.paper.meta_reviewed and bundle.manifest.paper.prior_works_reviewed):
            raise ValueError(f"manifest.json is not reviewed (meta_reviewed && prior_works_reviewed): {slug}")

        now = self._now()
        state = self.store.load_state()
        next_state = GraphState.model_validate(state.model_dump(mode="json"))
        (
            paper_nodes,
            relations,
            authors,
            authorships,
            patterns,
            pattern_classifications,
        ) = self._build_graph_records(bundle)
        events = self._build_events(
            slug,
            bundle.artifact_hash,
            next_state,
            paper_nodes,
            relations,
            authors,
            authorships,
            patterns,
            pattern_classifications,
            now,
        )
        self.store.save_state(next_state)
        self.store.append_events(events)
        return GraphPlanResult(
            slug=slug,
            events=events,
            paper_keys=[paper.paper_key for paper in paper_nodes],
            relation_keys=[relation.relation_key for relation in relations],
            author_keys=[author.author_key for author in authors],
            pattern_ids=[pattern.pattern_id for pattern in patterns],
        )

    def _build_graph_records(
        self, bundle: ArtifactBundle
    ) -> tuple[
        list[PaperNode],
        list[PriorWorkRelation],
        list[AuthorNode],
        list[AuthorshipRelation],
        list[PatternNode],
        list[PatternClassificationRelation],
    ]:
        paper = bundle.manifest.paper
        sci_pattern = bundle.sci_pattern
        prior_works = bundle.prior_works
        slug = bundle.manifest.slug
        source_paper_key = build_paper_key(paper.title, paper.year, paper.arxiv_id)

        main_paper = PaperNode(
            slug=slug,
            paper_key=source_paper_key,
            title=paper.title,
            year=paper.year,
            venue=paper.venue,
            arxiv_id=paper.arxiv_id,
            abstract=paper.abstract,
            synthesis_narrative=prior_works.synthesis_narrative,
            sci_pattern_reason=sci_pattern.reasoning,
            is_stub=False,
        )

        papers: dict[str, PaperNode] = {main_paper.paper_key: main_paper}
        relations: list[PriorWorkRelation] = []
        authors: dict[str, AuthorNode] = {}
        authorships: list[AuthorshipRelation] = []

        for order, name in enumerate(paper.authors):
            author_key = build_author_key(name)
            authors.setdefault(author_key, AuthorNode(author_key=author_key, name=name))
            authorships.append(
                AuthorshipRelation(
                    relation_key=build_authorship_key(author_key, source_paper_key),
                    author_key=author_key,
                    paper_key=source_paper_key,
                    author_order=order,
                    source_slug=slug,
                )
            )

        for entry in prior_works.prior_works:
            target_key = build_paper_key(entry.title, entry.year, entry.arxiv_id)
            papers.setdefault(
                target_key,
                PaperNode(
                    paper_key=target_key,
                    title=entry.title,
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
                    source_slug=slug,
                )
            )

            if has_usable_author_string(entry.authors):
                for order, name in enumerate(split_authors(entry.authors)):
                    author_key = build_author_key(name)
                    authors.setdefault(author_key, AuthorNode(author_key=author_key, name=name))
                    authorships.append(
                        AuthorshipRelation(
                            relation_key=build_authorship_key(author_key, target_key),
                            author_key=author_key,
                            paper_key=target_key,
                            author_order=order,
                            source_slug=slug,
                        )
                    )

        patterns: dict[str, PatternNode] = {}
        pattern_classifications: list[PatternClassificationRelation] = []

        primary_id = sci_pattern.primary_pattern.value
        patterns.setdefault(primary_id, PatternNode(pattern_id=primary_id, name=sci_pattern.primary_pattern_name))
        pattern_classifications.append(
            PatternClassificationRelation(
                relation_key=build_pattern_classification_key(source_paper_key, primary_id, "primary"),
                paper_key=source_paper_key,
                pattern_id=primary_id,
                role="primary",
                confidence=sci_pattern.confidence.value,
                source_slug=slug,
            )
        )

        secondary_names = list(sci_pattern.secondary_pattern_names)
        for index, secondary_pattern in enumerate(sci_pattern.secondary_patterns):
            pattern_id = secondary_pattern.value
            pattern_name = secondary_names[index] if index < len(secondary_names) else ""
            patterns.setdefault(pattern_id, PatternNode(pattern_id=pattern_id, name=pattern_name))
            pattern_classifications.append(
                PatternClassificationRelation(
                    relation_key=build_pattern_classification_key(source_paper_key, pattern_id, "secondary"),
                    paper_key=source_paper_key,
                    pattern_id=pattern_id,
                    role="secondary",
                    confidence=None,
                    source_slug=slug,
                )
            )

        return (
            list(papers.values()),
            relations,
            list(authors.values()),
            authorships,
            list(patterns.values()),
            pattern_classifications,
        )

    def _build_events(
        self,
        slug: str,
        artifact_hash: str,
        state: GraphState,
        papers: list[PaperNode],
        relations: list[PriorWorkRelation],
        authors: list[AuthorNode],
        authorships: list[AuthorshipRelation],
        patterns: list[PatternNode],
        pattern_classifications: list[PatternClassificationRelation],
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

        for author in authors:
            existing_author = state.authors.get(author.author_key)
            if existing_author is None or existing_author.model_dump(mode="json") != author.model_dump(mode="json"):
                events.append(
                    UpsertAuthorEvent(
                        event_id=f"upsert_author:{author.author_key}",
                        author_key=author.author_key,
                        source_slug=slug,
                        artifact_hash=artifact_hash,
                        created_at=now,
                        payload=author,
                    )
                )
            state.authors[author.author_key] = author

        for pattern in patterns:
            existing_pattern = state.patterns.get(pattern.pattern_id)
            if existing_pattern is None or existing_pattern.model_dump(mode="json") != pattern.model_dump(mode="json"):
                events.append(
                    UpsertPatternEvent(
                        event_id=f"upsert_pattern:{pattern.pattern_id}",
                        pattern_id=pattern.pattern_id,
                        source_slug=slug,
                        artifact_hash=artifact_hash,
                        created_at=now,
                        payload=pattern,
                    )
                )
            state.patterns[pattern.pattern_id] = pattern

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

        new_authorships = {authorship.relation_key: authorship for authorship in authorships}
        for authorship in authorships:
            existing_authorship = state.authorships.get(authorship.relation_key)
            if existing_authorship is None or existing_authorship.model_dump(mode="json") != authorship.model_dump(mode="json"):
                events.append(
                    UpsertAuthorshipEvent(
                        event_id=f"upsert_authorship:{authorship.author_key}:{authorship.paper_key}:{artifact_hash}",
                        author_key=authorship.author_key,
                        paper_key=authorship.paper_key,
                        source_slug=slug,
                        artifact_hash=artifact_hash,
                        created_at=now,
                        payload=authorship,
                    )
                )
            state.authorships[authorship.relation_key] = authorship

        stale_authorship_keys = [
            relation_key
            for relation_key, authorship in state.authorships.items()
            if authorship.source_slug == slug and relation_key not in new_authorships
        ]
        for relation_key in stale_authorship_keys:
            stale_authorship = state.authorships.pop(relation_key)
            events.append(
                DeleteAuthorshipEvent(
                    event_id=f"delete_authorship:{stale_authorship.author_key}:{stale_authorship.paper_key}",
                    author_key=stale_authorship.author_key,
                    paper_key=stale_authorship.paper_key,
                    source_slug=slug,
                    created_at=now,
                )
            )

        new_pattern_classifications = {
            classification.relation_key: classification for classification in pattern_classifications
        }
        for classification in pattern_classifications:
            existing_classification = state.pattern_classifications.get(classification.relation_key)
            if existing_classification is None or existing_classification.model_dump(mode="json") != classification.model_dump(
                mode="json"
            ):
                events.append(
                    UpsertPatternClassificationEvent(
                        event_id=f"upsert_pattern_classification:{classification.paper_key}:{classification.pattern_id}:{classification.role}:{artifact_hash}",
                        paper_key=classification.paper_key,
                        pattern_id=classification.pattern_id,
                        role=classification.role,
                        source_slug=slug,
                        artifact_hash=artifact_hash,
                        created_at=now,
                        payload=classification,
                    )
                )
            state.pattern_classifications[classification.relation_key] = classification

        stale_pattern_classification_keys = [
            relation_key
            for relation_key, classification in state.pattern_classifications.items()
            if classification.source_slug == slug and relation_key not in new_pattern_classifications
        ]
        for relation_key in stale_pattern_classification_keys:
            stale_classification = state.pattern_classifications.pop(relation_key)
            events.append(
                DeletePatternClassificationEvent(
                    event_id=f"delete_pattern_classification:{stale_classification.paper_key}:{stale_classification.pattern_id}:{stale_classification.role}",
                    paper_key=stale_classification.paper_key,
                    pattern_id=stale_classification.pattern_id,
                    role=stale_classification.role,
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


def build_author_key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def build_authorship_key(author_key: str, paper_key: str) -> str:
    return f"{author_key}:{paper_key}"


def build_pattern_classification_key(paper_key: str, pattern_id: str, role: str) -> str:
    return f"{paper_key}:{pattern_id}:{role}"


def normalize_title(title: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in title)
    return "-".join(normalized.split())


def split_authors(authors: str) -> list[str]:
    return [author.strip() for author in authors.split(",") if author.strip()]


def has_usable_author_string(authors: str) -> bool:
    stripped = authors.strip()
    if not stripped:
        return False
    return not stripped.lower().endswith("et al.")


def merge_paper(existing: PaperNode | None, incoming: PaperNode) -> PaperNode:
    if existing is None:
        return incoming
    merged = existing.model_copy(deep=True)
    incoming_payload = incoming.model_dump(mode="json")
    for key, value in incoming_payload.items():
        if key == "slug" and not value:
            continue
        if key in {"title", "venue", "arxiv_id", "abstract", "synthesis_narrative", "sci_pattern_reason"} and not value:
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
