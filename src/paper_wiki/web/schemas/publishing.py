from __future__ import annotations

from pydantic import BaseModel


class MarkdownDocumentResponse(BaseModel):
    document_id: str
    filename: str
    title: str
    created_at: str
    html_path: str
    cover_path: str | None = None
    html: str | None = None


class MarkdownPublishRequest(BaseModel):
    title: str | None = None
    author: str | None = None
    digest: str | None = None
    thumb_media_id: str | None = None
