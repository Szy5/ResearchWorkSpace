from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from paper_wiki.core.config import Settings
from paper_wiki.core.validation import validate_slug
from paper_wiki.publishing.cursor_render import render_blog_html
from paper_wiki.publishing.models import WeChatDraftOptions
from paper_wiki.publishing.wechat_publisher import publish_artifact_html_to_wechat
from paper_wiki.web.dependencies import get_job_manager, get_paper_repository, get_settings
from paper_wiki.web.schemas.job import JobResponse
from paper_wiki.web.schemas.paper import (
    PublishWeChatRequest,
    PublishWeChatResponse,
    RenderBlogHtmlRequest,
)
from paper_wiki.web.services.job_manager import JobManager
from paper_wiki.web.services.paper_repository import PaperRepository

router = APIRouter(prefix="/api/papers", tags=["publish"])


@router.post("/{slug}/blog/render-html", response_model=JobResponse, status_code=202)
def render_blog_html_endpoint(
    slug: str,
    payload: RenderBlogHtmlRequest,
    job_manager: JobManager = Depends(get_job_manager),
    repository: PaperRepository = Depends(get_paper_repository),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    clean_slug = validate_slug(slug)

    def task() -> dict[str, str]:
        html_path = render_blog_html(clean_slug, settings, theme=payload.theme)
        relative_name = html_path.name
        repository.mark_blog_html_generated(clean_slug, relative_name)
        return {"slug": clean_slug, "html_path": relative_name}

    job = job_manager.submit(slug=clean_slug, target="render_blog_html", task=task)
    return JobResponse.model_validate(job.model_dump())


@router.post("/{slug}/publish/wechat", response_model=PublishWeChatResponse)
def publish_wechat(
    slug: str,
    payload: PublishWeChatRequest,
    settings: Settings = Depends(get_settings),
) -> PublishWeChatResponse:
    clean_slug = validate_slug(slug)
    result = publish_artifact_html_to_wechat(
        settings,
        WeChatDraftOptions(
            slug=clean_slug,
            html_path=payload.html_path,
            title=payload.title,
            author=payload.author,
            digest=payload.digest,
            cover_path=Path(payload.cover_path) if payload.cover_path else None,
            thumb_media_id=payload.thumb_media_id,
            save_rendered=payload.save_rendered,
        ),
    )
    return PublishWeChatResponse(
        slug=result.slug,
        title=result.title,
        media_id=result.media_id,
        html_path=str(result.html_path),
        thumb_media_id=result.thumb_media_id,
        uploaded_image_count=result.uploaded_image_count,
        rendered_html_path=str(result.rendered_html_path) if result.rendered_html_path else None,
    )
