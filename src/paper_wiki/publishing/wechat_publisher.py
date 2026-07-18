from __future__ import annotations

from pathlib import Path

from paper_wiki.core.config import Settings
from paper_wiki.publishing.artifact_html import resolve_artifact_html
from paper_wiki.publishing.exceptions import HTMLValidationError, WeChatConfigError
from paper_wiki.publishing.html_processor import replace_local_images
from paper_wiki.publishing.models import WeChatDraftOptions, WeChatDraftResult
from paper_wiki.publishing.wechat_client import WeChatClient


def _derive_title(html_path: Path) -> str:
    title = html_path.stem
    if len(title) > 64:
        return title[:64]
    return title


def _resolve_optional_path(path: Path | None, *, project_root: Path, artifact_dir: Path) -> Path | None:
    if path is None:
        return None
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend([artifact_dir / path, project_root / path])

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return candidates[0].resolve()


def _write_rendered_html(artifact_dir: Path, source_html: Path, content: str) -> Path:
    rendered_path = artifact_dir / f"{source_html.stem}_wechat_rendered.html"
    rendered_path.write_text(content, encoding="utf-8")
    return rendered_path


def publish_artifact_html_to_wechat(
    settings: Settings,
    options: WeChatDraftOptions,
    *,
    client: WeChatClient | None = None,
) -> WeChatDraftResult:
    artifact = resolve_artifact_html(settings.resolved_artifacts_dir(), options.slug, options.html_path)

    if not settings.wechat_appid or not settings.wechat_secret:
        raise WeChatConfigError("WeChat credentials are missing: WECHAT_APPID and WECHAT_SECRET")

    thumb_media_id = options.thumb_media_id or settings.wechat_thumb_media_id
    cover_path = _resolve_optional_path(
        options.cover_path or settings.wechat_cover_path,
        project_root=settings.project_root.resolve(),
        artifact_dir=artifact.artifact_dir,
    )
    if not thumb_media_id:
        if cover_path is None:
            raise WeChatConfigError("cover image or thumb_media_id is required to create a WeChat draft")
        if not cover_path.exists() or not cover_path.is_file():
            raise WeChatConfigError(f"cover image does not exist: {cover_path}")

    wechat_client = client or WeChatClient(
        settings.wechat_appid,
        settings.wechat_secret,
        timeout=settings.wechat_request_timeout_seconds,
    )

    if not thumb_media_id:
        assert cover_path is not None
        thumb_media_id = wechat_client.upload_permanent_image(cover_path)

    processed = replace_local_images(
        artifact.content,
        html_file=artifact.html_path,
        upload_image=wechat_client.upload_article_image,
    )
    if not processed.content.strip():
        raise HTMLValidationError("processed HTML content is empty")

    rendered_html_path = None
    if options.save_rendered:
        rendered_html_path = _write_rendered_html(artifact.artifact_dir, artifact.html_path, processed.content)

    title = options.title or _derive_title(artifact.html_path)
    author = options.author if options.author is not None else settings.wechat_author
    payload = wechat_client.create_draft(
        title=title,
        content=processed.content,
        thumb_media_id=thumb_media_id,
        author=author,
        digest=options.digest,
    )

    return WeChatDraftResult(
        slug=options.slug,
        title=title,
        media_id=str(payload["media_id"]),
        html_path=artifact.html_path,
        thumb_media_id=thumb_media_id,
        uploaded_image_count=processed.uploaded_image_count,
        rendered_html_path=rendered_html_path,
    )
