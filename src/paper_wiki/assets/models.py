from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from paper_wiki.core.enums import ContributionType
from paper_wiki.core.validation import validate_slug


def _validate_relative_asset_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"path must be relative and stay inside the bundle: {value}")
    return value


class SourceFileHash(BaseModel):
    """Single raw source file recorded in manifest.json."""

    path: str
    sha256: str
    bytes: int

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_relative_asset_path(value)


class PaperAssetMeta(BaseModel):
    """Paper-level metadata stored in manifest.json."""

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
    added_date: date = Field(default_factory=date.today)
    blog_html_path: str | None = None
    blog_html_generated_at: str | None = None

    @model_validator(mode="after")
    def _migrate_legacy_reviewed_flag(self) -> "PaperAssetMeta":
        """Manifests written before the two-flag review model only had `reviewed`.

        If it was already True but both new sub-flags are still at their default
        (meaning this manifest predates them), treat both as already reviewed
        instead of silently reverting the paper to "needs review".
        """
        if self.reviewed and not self.meta_reviewed and not self.prior_works_reviewed:
            object.__setattr__(self, "meta_reviewed", True)
            object.__setattr__(self, "prior_works_reviewed", True)
        return self


class SourceProvenance(BaseModel):
    """Layer0 input provenance for manifest.json."""

    raw_dir: str
    entry_file: str
    source_files: list[SourceFileHash] = Field(default_factory=list)
    unresolved_inputs: list[str] = Field(default_factory=list)

    @field_validator("entry_file")
    @classmethod
    def validate_entry_file(cls, value: str) -> str:
        return _validate_relative_asset_path(value)


class AssetFileIndex(BaseModel):
    """Relative file index for the assets bundle."""

    paper_text: str = "assets/paper.md"
    sections: str = "assets/sections.json"
    figures: str = "assets/figures/manifest.json"
    references: str = "assets/references.json"

    @field_validator("*")
    @classmethod
    def validate_paths(cls, value: str) -> str:
        return _validate_relative_asset_path(value)


class AssetCounts(BaseModel):
    """Lightweight manifest counts."""

    sections: int = 0
    figures: int = 0
    references: int = 0


class ParserInfo(BaseModel):
    """Parser metadata recorded in manifest.json."""

    name: str = "paper-wiki-latex-parser"
    version: str = "v1"


class AssetsManifest(BaseModel):
    """Top-level manifest for one paper assets bundle."""

    schema_version: Literal["paper-wiki-assets-v1"] = "paper-wiki-assets-v1"
    slug: str
    created_at: str
    updated_at: str
    paper: PaperAssetMeta
    source: SourceProvenance
    files: AssetFileIndex = Field(default_factory=AssetFileIndex)
    counts: AssetCounts
    parser: ParserInfo = Field(default_factory=ParserInfo)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return validate_slug(value)


class SourceSpan(BaseModel):
    """Best-effort source location for a section."""

    file: str = ""
    line_start: int | None = None
    line_end: int | None = None


class SectionAsset(BaseModel):
    """A section-level text asset. This deliberately avoids paragraph/block granularity."""

    id: str
    type: str
    title: str
    level: int
    order: int
    parent_id: str = ""
    source: SourceSpan | None = None
    text: str
    labels: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    figure_ids: list[str] = Field(default_factory=list)


class SectionsDoc(BaseModel):
    """assets/sections.json."""

    sections: list[SectionAsset] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "SectionsDoc":
        ids = [section.id for section in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("section ids must be unique")
        return self


class FigureAsset(BaseModel):
    """A single figure copied or rendered into assets/figures."""

    id: str
    label: str = ""
    caption: str = ""
    source_path: str
    asset_path: str = ""
    section_id: str = ""
    status: str = "referenced"
    source_sha256: str = ""
    media_type: str = ""

    @field_validator("source_path", "asset_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value:
            return value
        return _validate_relative_asset_path(value)

    @field_validator("asset_path")
    @classmethod
    def validate_asset_path(cls, value: str) -> str:
        if value and not value.startswith("assets/figures/"):
            raise ValueError("figure asset_path must be under assets/figures/")
        return value


class FiguresDoc(BaseModel):
    """assets/figures/manifest.json."""

    figures: list[FigureAsset] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "FiguresDoc":
        ids = [figure.id for figure in self.figures]
        if len(ids) != len(set(ids)):
            raise ValueError("figure ids must be unique")
        return self


class CitationContext(BaseModel):
    """A lightweight citation context from paper text."""

    section_id: str = ""
    text: str = ""


class ReferenceEntry(BaseModel):
    """A reference entry derived from .bib/.bbl plus citation contexts."""

    key: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
    arxiv_id: str = ""
    url: str = ""
    raw_bibtex: str = ""
    citation_contexts: list[CitationContext] = Field(default_factory=list)


class ReferencesDoc(BaseModel):
    """assets/references.json."""

    references: list[ReferenceEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "ReferencesDoc":
        keys = [reference.key for reference in self.references]
        if len(keys) != len(set(keys)):
            raise ValueError("reference keys must be unique")
        return self


ASSET_CONTEXT_TARGETS: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract",),
    "introduction": ("introduction", "intro"),
    "related_work": ("related work", "background"),
    "method": ("method", "approach", "model", "framework", "system"),
    "experiments": ("experiment", "evaluation", "result", "analysis"),
    "conclusion": ("conclusion", "discussion", "future work"),
}
ASSET_CONTEXT_ORDER = ("abstract", "introduction", "related_work", "method", "experiments", "conclusion")


class PaperAssetsBundle(BaseModel):
    """Canonical Layer 1 input loaded from artifacts/{slug}/assets."""

    slug: str
    artifact_dir: Path
    manifest: AssetsManifest
    paper_markdown: str
    sections: SectionsDoc
    figures: FiguresDoc
    references: ReferencesDoc

    @property
    def title(self) -> str:
        return self.manifest.paper.title or self.slug

    @property
    def authors(self) -> list[str]:
        return self.manifest.paper.authors

    @property
    def abstract(self) -> str:
        return self.manifest.paper.abstract

    @property
    def source_files(self) -> list[str]:
        return [source.path for source in self.manifest.source.source_files]

    @property
    def entry_file(self) -> str:
        return self.manifest.source.entry_file

    @property
    def matched_sections(self) -> dict[str, bool]:
        by_target = self.sections_by_target()
        return {target: target in by_target for target in ASSET_CONTEXT_TARGETS}

    def sections_by_target(self) -> dict[str, str]:
        matched: dict[str, str] = {}
        for section in self.sections.sections:
            normalized = section.title.lower().replace("_", " ")
            candidates = (section.type.lower(), normalized)
            for target, keywords in ASSET_CONTEXT_TARGETS.items():
                if target in matched:
                    continue
                if target == "abstract" and section.type == "abstract":
                    matched[target] = section.text
                    continue
                if any(keyword in candidate for keyword in keywords for candidate in candidates):
                    matched[target] = section.text
                    break
        return matched

    def llm_context(self, max_chars: int | None = None) -> str:
        """Return a stable text view for downstream LLM prompts."""
        by_target = self.sections_by_target()
        parts: list[tuple[str, str]] = []
        if self.abstract:
            parts.append(("Abstract", self.abstract))
        for key in ASSET_CONTEXT_ORDER[1:]:
            if content := by_target.get(key):
                parts.append((key.replace("_", " ").title(), content))
        if not parts and self.paper_markdown.strip():
            text = self.paper_markdown.strip()
        else:
            text = "\n\n".join(f"## {title}\n\n{content.strip()}" for title, content in parts if content.strip())
        if max_chars is not None and max_chars > 0 and len(text) > max_chars:
            return text[:max_chars].rsplit(" ", 1)[0].strip() + "\n\n[TRUNCATED]"
        return text

    def estimated_tokens(self, max_chars: int | None = None) -> int:
        return max(1, int(len(self.llm_context(max_chars=max_chars)) / 3.5))


class AssetsBuildResult(BaseModel):
    """Paths returned by one deterministic assets build."""

    slug: str
    artifact_dir: Path
    manifest_path: Path
    paper_path: Path
    sections_path: Path
    figures_dir: Path
    figures_manifest_path: Path
    references_path: Path
