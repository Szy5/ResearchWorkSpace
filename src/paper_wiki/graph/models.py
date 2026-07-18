from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from paper_wiki.assets.models import AssetsManifest
from paper_wiki.core.models import PriorWorksDoc, SciPatternDoc

PriorWorkRelationType = Literal[
    "BASELINE",
    "INSPIRATION",
    "GAP_IDENTIFICATION",
    "FOUNDATION",
    "EXTENSION",
    "RELATED_PROBLEM",
]

PatternClassificationRole = Literal["primary", "secondary"]


class ArtifactBundle(BaseModel):
    """一篇论文的 reviewed Layer1 语义产物集合及其路径。"""

    slug: str
    manifest: AssetsManifest
    prior_works: PriorWorksDoc
    sci_pattern: SciPatternDoc
    manifest_path: Path
    summary_path: Path
    prior_works_path: Path
    sci_pattern_path: Path
    artifact_hash: str


class PaperNode(BaseModel):
    """Neo4j Paper 节点的规范化载荷。"""

    slug: str = ""
    paper_key: str
    title: str
    year: int | None = None
    venue: str = ""
    arxiv_id: str = ""
    abstract: str = ""
    synthesis_narrative: str = ""
    sci_pattern_reason: str = ""
    is_stub: bool = False


class AuthorNode(BaseModel):
    """Neo4j Author 节点的规范化载荷。"""

    author_key: str
    name: str


class PatternNode(BaseModel):
    """Neo4j Pattern 节点的规范化载荷。"""

    pattern_id: str
    name: str


class PriorWorkRelation(BaseModel):
    """Neo4j 论文间前作关系。"""

    relation_key: str
    relation_type: PriorWorkRelationType
    source_paper_key: str
    target_paper_key: str
    source_slug: str


class AuthorshipRelation(BaseModel):
    """Neo4j Author -> Paper 署名关系。"""

    relation_key: str
    author_key: str
    paper_key: str
    author_order: int
    source_slug: str


class PatternClassificationRelation(BaseModel):
    """Neo4j Paper -> Pattern 范式分类关系。"""

    relation_key: str
    paper_key: str
    pattern_id: str
    role: PatternClassificationRole
    confidence: str | None = None
    source_slug: str


class GraphState(BaseModel):
    """本地图谱快照，用于生成增量事件。"""

    papers: dict[str, PaperNode] = Field(default_factory=dict)
    relations: dict[str, PriorWorkRelation] = Field(default_factory=dict)
    authors: dict[str, AuthorNode] = Field(default_factory=dict)
    patterns: dict[str, PatternNode] = Field(default_factory=dict)
    authorships: dict[str, AuthorshipRelation] = Field(default_factory=dict)
    pattern_classifications: dict[str, PatternClassificationRelation] = Field(default_factory=dict)


class UpsertPaperEvent(BaseModel):
    event_id: str
    op: Literal["upsert_paper"] = "upsert_paper"
    paper_key: str
    source_slug: str
    artifact_hash: str
    created_at: str
    payload: PaperNode


class UpsertPriorWorkRelationEvent(BaseModel):
    event_id: str
    op: Literal["upsert_prior_work_relation"] = "upsert_prior_work_relation"
    relation_type: PriorWorkRelationType
    source_paper_key: str
    target_paper_key: str
    source_slug: str
    artifact_hash: str
    created_at: str
    payload: PriorWorkRelation


class DeletePriorWorkRelationEvent(BaseModel):
    event_id: str
    op: Literal["delete_prior_work_relation"] = "delete_prior_work_relation"
    relation_type: PriorWorkRelationType
    source_paper_key: str
    target_paper_key: str
    source_slug: str
    created_at: str


class UpsertAuthorEvent(BaseModel):
    event_id: str
    op: Literal["upsert_author"] = "upsert_author"
    author_key: str
    source_slug: str
    artifact_hash: str
    created_at: str
    payload: AuthorNode


class UpsertPatternEvent(BaseModel):
    event_id: str
    op: Literal["upsert_pattern"] = "upsert_pattern"
    pattern_id: str
    source_slug: str
    artifact_hash: str
    created_at: str
    payload: PatternNode


class UpsertAuthorshipEvent(BaseModel):
    event_id: str
    op: Literal["upsert_authorship"] = "upsert_authorship"
    author_key: str
    paper_key: str
    source_slug: str
    artifact_hash: str
    created_at: str
    payload: AuthorshipRelation


class DeleteAuthorshipEvent(BaseModel):
    event_id: str
    op: Literal["delete_authorship"] = "delete_authorship"
    author_key: str
    paper_key: str
    source_slug: str
    created_at: str


class UpsertPatternClassificationEvent(BaseModel):
    event_id: str
    op: Literal["upsert_pattern_classification"] = "upsert_pattern_classification"
    paper_key: str
    pattern_id: str
    role: PatternClassificationRole
    source_slug: str
    artifact_hash: str
    created_at: str
    payload: PatternClassificationRelation


class DeletePatternClassificationEvent(BaseModel):
    event_id: str
    op: Literal["delete_pattern_classification"] = "delete_pattern_classification"
    paper_key: str
    pattern_id: str
    role: PatternClassificationRole
    source_slug: str
    created_at: str


GraphEvent = (
    UpsertPaperEvent
    | UpsertPriorWorkRelationEvent
    | DeletePriorWorkRelationEvent
    | UpsertAuthorEvent
    | UpsertPatternEvent
    | UpsertAuthorshipEvent
    | DeleteAuthorshipEvent
    | UpsertPatternClassificationEvent
    | DeletePatternClassificationEvent
)


class GraphPlanResult(BaseModel):
    """一次 graph plan 的结果。"""

    slug: str
    events: list[GraphEvent] = Field(default_factory=list)
    paper_keys: list[str] = Field(default_factory=list)
    relation_keys: list[str] = Field(default_factory=list)
    author_keys: list[str] = Field(default_factory=list)
    pattern_ids: list[str] = Field(default_factory=list)


class ApplyCheckpoint(BaseModel):
    """JSONL 应用进度。"""

    applied_line_count: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"))
