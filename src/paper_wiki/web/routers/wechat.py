from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from paper_wiki.core.config import Settings
from paper_wiki.core.validation import validate_slug
from paper_wiki.publishing import paper_wechat
from paper_wiki.web.dependencies import get_job_manager, get_settings
from paper_wiki.web.schemas.job import JobResponse
from paper_wiki.web.services.job_manager import JobManager

router = APIRouter(tags=["wechat"])


class PrepareRequest(BaseModel):
    title: str | None = None
    digest: str | None = None
    author: str | None = None
    regenerate_headline: bool = True
    publish: bool = False


class PackagePatch(BaseModel):
    title: str | None = None
    digest: str | None = None
    author: str | None = None


@router.get("/api/publishing/wechat/config")
def wechat_config(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {
        "configured": bool(settings.wechat_appid and settings.wechat_secret),
        "default_author": settings.wechat_author or "",
        "title_limit": paper_wechat.TITLE_LIMIT,
        "digest_limit": paper_wechat.DIGEST_LIMIT,
        "author_limit": paper_wechat.AUTHOR_LIMIT,
    }


@router.get("/api/papers/{slug}/wechat")
def get_package(slug: str, settings: Settings = Depends(get_settings)) -> dict[str, Any] | None:
    package = paper_wechat.load_package(settings, validate_slug(slug))
    return paper_wechat.package_to_dict(package, settings) if package else None


@router.post("/api/papers/{slug}/wechat/prepare", response_model=JobResponse, status_code=202)
def prepare_package(
    slug: str,
    payload: PrepareRequest,
    settings: Settings = Depends(get_settings),
    job_manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    clean_slug = validate_slug(slug)

    def task() -> dict[str, Any]:
        package = paper_wechat.prepare_paper_wechat(
            settings,
            clean_slug,
            title=payload.title or None,
            digest=payload.digest or None,
            author=payload.author or None,
            regenerate_headline=payload.regenerate_headline,
        )
        if payload.publish:
            package = paper_wechat.publish_paper_wechat(settings, clean_slug)
        return paper_wechat.package_to_dict(package, settings)

    steps = paper_wechat.PREPARE_STEPS + (paper_wechat.PUBLISH_STEPS if payload.publish else [])
    job = job_manager.submit(
        slug=clean_slug,
        target="wechat_publish" if payload.publish else "wechat_prepare",
        task=task,
        steps=steps,
    )
    return JobResponse.model_validate(job.model_dump())


@router.post("/api/papers/{slug}/wechat/publish", response_model=JobResponse, status_code=202)
def publish_package(
    slug: str,
    settings: Settings = Depends(get_settings),
    job_manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    clean_slug = validate_slug(slug)
    if paper_wechat.load_package(settings, clean_slug) is None:
        raise ValueError("请先生成公众号预览")

    def task() -> dict[str, Any]:
        return paper_wechat.package_to_dict(paper_wechat.publish_paper_wechat(settings, clean_slug), settings)

    job = job_manager.submit(slug=clean_slug, target="wechat_publish", task=task, steps=paper_wechat.PUBLISH_STEPS)
    return JobResponse.model_validate(job.model_dump())


@router.patch("/api/papers/{slug}/wechat")
def patch_package(slug: str, payload: PackagePatch, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    package = paper_wechat.update_package_fields(
        settings,
        validate_slug(slug),
        title=payload.title,
        digest=payload.digest,
        author=payload.author,
    )
    return paper_wechat.package_to_dict(package, settings)


@router.post("/api/papers/{slug}/wechat/cover")
async def upload_cover(
    slug: str,
    file: Annotated[UploadFile, File()],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    package = paper_wechat.set_custom_cover(settings, validate_slug(slug), file.filename or "cover.jpg", await file.read())
    return paper_wechat.package_to_dict(package, settings)


@router.delete("/api/papers/{slug}/wechat/cover")
def reset_cover(slug: str, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    package = paper_wechat.reset_cover(settings, validate_slug(slug))
    return paper_wechat.package_to_dict(package, settings)


@router.get("/api/papers/{slug}/wechat/preview", response_class=HTMLResponse)
def preview(slug: str, settings: Settings = Depends(get_settings)) -> HTMLResponse:
    clean_slug = validate_slug(slug)
    if paper_wechat.load_package(settings, clean_slug) is None:
        raise ValueError("请先生成公众号预览")
    html = paper_wechat.preview_html(settings, clean_slug, file_url_prefix=f"/api/papers/{clean_slug}/files/")
    page = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>body{margin:0;background:#fff;padding:16px 0;}</style></head>"
        f"<body>{html}</body></html>"
    )
    return HTMLResponse(page)
