from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ArtifactHTML(BaseModel):
    slug: str
    artifact_dir: Path
    html_path: Path
    relative_html_path: str
    content: str


class WeChatDraftOptions(BaseModel):
    slug: str
    html_path: str
    title: str | None = None
    author: str | None = None
    digest: str | None = None
    cover_path: Path | None = None
    thumb_media_id: str | None = None
    save_rendered: bool = False


class ProcessedHTML(BaseModel):
    content: str
    uploaded_image_count: int = 0
    image_map: dict[str, str] = Field(default_factory=dict)


class WeChatDraftResult(BaseModel):
    slug: str
    title: str
    media_id: str
    html_path: Path
    thumb_media_id: str
    uploaded_image_count: int = 0
    rendered_html_path: Path | None = None
