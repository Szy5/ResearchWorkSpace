from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from paper_wiki.core.config import Settings
from paper_wiki.publishing.models import WeChatDraftOptions
from paper_wiki.publishing.paper_wechat import PUBLISH_STEPS
from paper_wiki.publishing.wechat_publisher import publish_artifact_html_to_wechat
from paper_wiki.web.dependencies import get_job_manager, get_settings
from paper_wiki.web.schemas.job import JobResponse
from paper_wiki.web.schemas.publishing import MarkdownDocumentResponse, MarkdownPublishRequest
from paper_wiki.web.services.job_manager import JobManager
from paper_wiki.web.services.markdown_publishing import MarkdownPublishingService

router = APIRouter(prefix="/api/publishing/markdown", tags=["publishing"])


@router.get("", response_model=list[MarkdownDocumentResponse])
def list_documents(
    settings: Settings = Depends(get_settings),
) -> list[MarkdownDocumentResponse]:
    service = MarkdownPublishingService(settings)
    return [MarkdownDocumentResponse.model_validate(item) for item in service.list()]


@router.post("/render", response_model=MarkdownDocumentResponse)
async def render_markdown(
    file: Annotated[UploadFile, File()],
    images: Annotated[list[UploadFile] | None, File()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
    theme: Annotated[str, Form()] = "摸鱼绿",
    settings: Settings = Depends(get_settings),
) -> MarkdownDocumentResponse:
    if theme != "摸鱼绿":
        raise ValueError("当前 Web 页面仅支持摸鱼绿主题")
    service = MarkdownPublishingService(settings)
    image_payloads = [(item.filename or "image.png", await item.read()) for item in images or []]
    cover_payload = (cover.filename or "cover.png", await cover.read()) if cover else None
    result = service.render(
        filename=file.filename or "article.md",
        content=await file.read(),
        images=image_payloads,
        cover=cover_payload,
    )
    return MarkdownDocumentResponse.model_validate(result)


@router.get("/{document_id}", response_model=MarkdownDocumentResponse)
def get_document(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> MarkdownDocumentResponse:
    return MarkdownDocumentResponse.model_validate(MarkdownPublishingService(settings).get(document_id))


@router.get("/{document_id}/preview", response_class=HTMLResponse)
def preview_document(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    html = MarkdownPublishingService(settings).html_path(document_id).read_text(encoding="utf-8")
    return HTMLResponse(html)


@router.post("/{document_id}/publish", response_model=JobResponse, status_code=202)
def publish_document(
    document_id: str,
    payload: MarkdownPublishRequest,
    settings: Settings = Depends(get_settings),
    job_manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    service = MarkdownPublishingService(settings)
    document = service.get(document_id, include_html=False)

    def task() -> dict[str, object]:
        result = publish_artifact_html_to_wechat(
            settings,
            WeChatDraftOptions(
                slug=".publishing",
                html_path=f"{document_id}/article.html",
                title=payload.title or str(document["title"]),
                author=payload.author,
                digest=payload.digest,
                cover_path=document.get("cover_path"),
                thumb_media_id=payload.thumb_media_id,
                save_rendered=True,
            ),
        )
        return result.model_dump(mode="json")

    job = job_manager.submit(slug=document_id, target="markdown_publish", task=task, steps=PUBLISH_STEPS)
    return JobResponse.model_validate(job.model_dump())
