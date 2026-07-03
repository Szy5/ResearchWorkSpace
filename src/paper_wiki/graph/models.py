from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from paper_wiki.core.models import PriorWorksDoc, SciPatternDoc, SummaryFrontmatter

PriorWorkRelationType = Literal[
    "BASELINE",
    "INSPIRATION",
    "GAP_IDENTIFICATION",
    "FOUNDATION",
    "EXTENSION",
    "RELATED_PROBLEM",
]


class ArtifactBundle(BaseModel):
    """一篇论文的 reviewed Layer1 三件套及其路径。"""

    slug: str
    summary: SummaryFrontmatter
    prior_works: PriorWorksDoc
    sci_pattern: SciPatternDoc
    summary_path: Path
    prior_works_path: Path
    sci_pattern_path: Path
    artifact_hash: str


class PaperNode(BaseModel):
    """Neo4j Paper 节点的规范化载荷。"""

    slug: str = ""
    paper_key: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    arxiv_id: str = ""
    primary_pattern_id: str = ""
    primary_pattern_name: str = ""
    secondary_pattern_ids: list[str] = Field(default_factory=list)
    secondary_pattern_names: list[str] = Field(default_factory=list)
    synthesis_narrative: str = ""
    sci_pattern_reason: str = ""
    is_stub: bool = False
    added_date: str | None = None


class PriorWorkRelation(BaseModel):
    """Neo4j 论文间前作关系。"""

    relation_key: str
    relation_type: PriorWorkRelationType
    source_paper_key: str
    target_paper_key: str
    source_slug: str


class GraphState(BaseModel):
    """本地图谱快照，用于生成增量事件。"""

    papers: dict[str, PaperNode] = Field(default_factory=dict)
    relations: dict[str, PriorWorkRelation] = Field(default_factory=dict)


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


GraphEvent = UpsertPaperEvent | UpsertPriorWorkRelationEvent | DeletePriorWorkRelationEvent


class GraphPlanResult(BaseModel):
    """一次 graph plan 的结果。"""

    slug: str
    events: list[GraphEvent] = Field(default_factory=list)
    paper_keys: list[str] = Field(default_factory=list)
    relation_keys: list[str] = Field(default_factory=list)


class ApplyCheckpoint(BaseModel):
    """JSONL 应用进度。"""

    applied_line_count: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"))
