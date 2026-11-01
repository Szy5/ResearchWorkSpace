from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
import uuid

from paper_wiki.core.config import Settings
from paper_wiki.publishing.markdown_renderer import render_markdown_for_wechat


DOCUMENT_ID_RE = re.compile(r"^[a-f0-9]{32}$")


class MarkdownPublishingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.resolved_artifacts_dir() / ".publishing"

    def render(
        self,
        *,
        filename: str,
        content: bytes,
        images: list[tuple[str, bytes]] | None = None,
        cover: tuple[str, bytes] | None = None,
    ) -> dict[str, Any]:
        clean_name = Path(filename).name
        if Path(clean_name).suffix.lower() not in {".md", ".markdown"}:
            raise ValueError("只支持 .md 或 .markdown 文件")
        if len(content) > 5 * 1024 * 1024:
            raise ValueError("Markdown 文件不能超过 5 MB")
        try:
            markdown_text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Markdown 文件必须使用 UTF-8 编码") from exc

        document_id = uuid.uuid4().hex
        document_dir = self.root / document_id
        document_dir.mkdir(parents=True, exist_ok=False)
        (document_dir / "source.md").write_text(markdown_text, encoding="utf-8")

        for image_name, image_content in images or []:
            safe_name = Path(image_name).name
            if Path(safe_name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif"}:
                raise ValueError(f"不支持的正文图片格式：{safe_name}")
            (document_dir / safe_name).write_bytes(image_content)

        cover_path: str | None = None
        if cover:
            cover_name, cover_content = cover
            suffix = Path(cover_name).suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png"}:
                raise ValueError("封面图只支持 JPG 或 PNG")
            target = document_dir / f"cover{suffix}"
            target.write_bytes(cover_content)
            cover_path = str(target)

        rendered = render_markdown_for_wechat(
            markdown_text,
            fallback_title=Path(clean_name).stem,
            asset_dir=document_dir,
        )
        html_path = document_dir / "article.html"
        html_path.write_text(rendered.html, encoding="utf-8")
        metadata = {
            "document_id": document_id,
            "filename": clean_name,
            "title": rendered.title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "html_path": "article.html",
            "cover_path": cover_path,
        }
        (document_dir / "meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {**metadata, "html": rendered.html}

    def get(self, document_id: str, *, include_html: bool = True) -> dict[str, Any]:
        document_dir = self._document_dir(document_id)
        metadata = json.loads((document_dir / "meta.json").read_text(encoding="utf-8"))
        if include_html:
            metadata["html"] = (document_dir / "article.html").read_text(encoding="utf-8")
        return metadata

    def list(self, *, limit: int = 30) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        documents: list[dict[str, Any]] = []
        for meta_path in self.root.glob("*/meta.json"):
            try:
                documents.append(json.loads(meta_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        documents.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return documents[: max(1, min(limit, 100))]

    def html_path(self, document_id: str) -> Path:
        return self._document_dir(document_id) / "article.html"

    def _document_dir(self, document_id: str) -> Path:
        if not DOCUMENT_ID_RE.fullmatch(document_id):
            raise ValueError("无效的发布文档 ID")
        document_dir = self.root / document_id
        if not (document_dir / "meta.json").is_file():
            raise ValueError("发布文档不存在")
        return document_dir
