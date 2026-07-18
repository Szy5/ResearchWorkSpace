from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic import field_validator

from paper_wiki.core.enums import ContributionType, PriorWorkRole
from paper_wiki.ingestion.pipeline import TARGET_ALIASES


class PaperMetaDTO(BaseModel):
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    venue: str = ""
    arxiv_id: str = ""
    tags: list[str] = Field(default_factory=list)
    contribution_type: ContributionType | None = None
    reviewed: bool = False
    meta_reviewed: bool = False
    prior_works_reviewed: bool = False
    added_date: str = ""
    blog_html_path: str | None = None
    blog_html_generated_at: str | None = None


class PaperListItem(BaseModel):
    slug: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    venue: str = ""
    reviewed: bool = False
    updated_at: str
    has_summary: bool = False
    has_prior_works: bool = False
    has_sci_pattern: bool = False
    primary_pattern: str = ""
    primary_pattern_name: str = ""


class PaperDetail(BaseModel):
    slug: str
    updated_at: str
    meta: PaperMetaDTO
    summary: str = ""
    prior_works: dict[str, Any] | None = None
    sci_pattern: dict[str, Any] | None = None
    references_count: int = 0
    figures_count: int = 0
    sections_count: int = 0


class PaperMetaPatch(BaseModel):
    expected_updated_at: str
    title: str | None = None
    authors: list[str] | None = None
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    arxiv_id: str | None = None
    tags: list[str] | None = None
    contribution_type: ContributionType | None = None
    meta_reviewed: bool | None = None
    prior_works_reviewed: bool | None = None


class SummaryPatch(BaseModel):
    expected_updated_at: str
    summary: str


class PriorWorkEntryDTO(BaseModel):
    title: str
    authors: str
    year: int | None = None
    arxiv_id: str = ""
    role: PriorWorkRole
    relationship_sentence: str


class PriorWorksPatch(BaseModel):
    expected_updated_at: str
    prior_works: list[PriorWorkEntryDTO]
    synthesis_narrative: str


class IngestRequest(BaseModel):
    overwrite: bool = False
    only: list[str] | None = None
    summary_prompt: str | None = "paper_summary_v3.py"
    prior_works_prompt: str | None = "prior_work_prompt.py"
    sci_pattern_prompt: str | None = "sci_pattern_classify_prompt.py"

    @field_validator("only")
    @classmethod
    def validate_only_targets(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        invalid = [target for target in value if target.strip().lower() not in TARGET_ALIASES]
        if invalid:
            allowed = ", ".join(sorted(TARGET_ALIASES))
            raise ValueError(f"Unknown semantic artifact target(s): {', '.join(invalid)}. Allowed values: {allowed}")
        return value


class RenderBlogHtmlRequest(BaseModel):
    theme: str | None = None


class RenderBlogHtmlResult(BaseModel):
    slug: str
    html_path: str


class PublishWeChatRequest(BaseModel):
    html_path: str
    title: str | None = None
    author: str | None = None
    digest: str | None = None
    cover_path: str | None = None
    thumb_media_id: str | None = None
    save_rendered: bool = False


class PublishWeChatResponse(BaseModel):
    slug: str
    title: str
    media_id: str
    html_path: str
    thumb_media_id: str
    uploaded_image_count: int = 0
    rendered_html_path: str | None = None
