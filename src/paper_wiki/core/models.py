from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from paper_wiki.core.enums import (
    ConfidenceLevel,
    ContributionType,
    PatternID,
    PriorWorkRole,
)


class PaperMeta(BaseModel):
    """论文级元数据；未来 Layer2 index 和图谱节点可以复用。"""

    slug: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    arxiv_id: str = ""
    tags: list[str] = Field(default_factory=list)
    primary_pattern: PatternID | None = None
    secondary_patterns: list[PatternID] = Field(default_factory=list)
    contribution_type: ContributionType | None = None
    reviewed: bool = False
    added_date: date = Field(default_factory=date.today)


class ParsedPaper(BaseModel):
    """Layer0 解析结果，是后续三个 Layer1 生成器的共同输入。"""

    slug: str
    raw_text: str
    estimated_tokens: int
    source_files: list[str]
    matched_sections: dict[str, bool]
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    entry_file: str = ""


class PriorWorkEntry(BaseModel):
    """单条前作关系，最终会成为 Layer2 科学发现图谱的一条候选边。"""

    title: str
    authors: str
    year: int | None = None
    arxiv_id: str = ""
    role: PriorWorkRole
    relationship_sentence: str


class PriorWorksDoc(BaseModel):
    """prior_works.json 的完整结构。"""

    prior_works: list[PriorWorkEntry] = Field(default_factory=list)
    synthesis_narrative: str

    @field_validator("prior_works")
    @classmethod
    def validate_prior_work_count(cls, value: list[PriorWorkEntry]) -> list[PriorWorkEntry]:
        """至少需要一条前作；否则说明生成结果不可用于后续审查。"""
        if not value:
            raise ValueError("prior_works must not be empty")
        return value


class SciPatternDoc(BaseModel):
    """sci_pattern.json 的完整结构，记录主要/次要科学创新范式。"""

    primary_pattern: PatternID
    primary_pattern_name: str = ""
    secondary_patterns: list[PatternID] = Field(default_factory=list)
    secondary_pattern_names: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    reasoning: str


class SummaryFrontmatter(BaseModel):
    """summary.md 的 YAML frontmatter；reviewed 默认必须是 false。"""

    slug: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    arxiv_id: str = ""
    tags: list[str] = Field(default_factory=list)
    contribution_type: ContributionType | None = None
    reviewed: bool = False
    added_date: date = Field(default_factory=date.today)


class IngestResult(BaseModel):
    """一次 ingest 的返回对象，包含产物路径和 Layer0 解析摘要。"""

    slug: str
    artifact_dir: Path
    summary_path: Path
    prior_works_path: Path
    sci_pattern_path: Path
    parsed: ParsedPaper
