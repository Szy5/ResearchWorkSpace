"""One-click WeChat publishing for a paper's summary.md.

Everything is written under ``artifacts/{slug}/wechat/``:

- ``article.md``    summary.md with formulas stripped, figures localized, lead figure + info card prepended
- ``article.html``  Cursor headless + gzh-design fragment (relative image paths)
- ``images/``       article figures re-encoded for WeChat (JPEG, < 1MB)
- ``cover.jpg``     generated (or uploaded) cover
- ``package.json``  title / digest / author / publish state
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, field_validator

from paper_wiki.assets.models import AssetsManifest, PaperAssetMeta
from paper_wiki.core import progress
from paper_wiki.core.config import Settings
from paper_wiki.core.progress import StepSpec
from paper_wiki.core.validation import validate_slug
from paper_wiki.ingestion.llm_client import LLMClient, build_llm_client
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path
from paper_wiki.publishing.cover_generator import generate_wechat_cover
from paper_wiki.publishing.cursor_render import render_markdown_html
from paper_wiki.publishing.exceptions import CursorRenderError, PublishingError, WeChatConfigError
from paper_wiki.publishing.html_processor import (
    replace_local_images,
    sanitize_wechat_blog_html,
    validate_wechat_html,
)
from paper_wiki.publishing.wechat_client import WeChatClient
from paper_wiki.publishing.wechat_limits import AUTHOR_LIMIT, DIGEST_LIMIT, TITLE_LIMIT, fit_wechat_length

logger = logging.getLogger(__name__)

WECHAT_DIRNAME = "wechat"
PACKAGE_FILE = "package.json"
ARTICLE_FILE = "article.html"
SOURCE_FILE = "article.md"
COVER_FILE = "cover.jpg"
# Sections appended to summary.md for the knowledge base; not meant for readers.
APPENDIX_HEADINGS = ("科学发现范式", "先前工作分析")
MAX_IMAGE_BYTES = 950 * 1024
MAX_IMAGE_WIDTH = 1280
_DISPLAY_MATH_RE = re.compile(r"\$\$[\s\S]+?\$\$")
_INLINE_MATH_RE = re.compile(r"(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

PREPARE_STEPS = [
    StepSpec("read", "读取精读笔记"),
    StepSpec("headline", "生成标题与摘要", external="LLM"),
    StepSpec("adapt", "准备公众号正文"),
    StepSpec("images", "处理正文图片"),
    StepSpec("render", "Cursor 排版 HTML", external="Cursor"),
    StepSpec("cover", "生成封面"),
]
PUBLISH_STEPS = [
    StepSpec("upload_cover", "上传封面", external="微信 API"),
    StepSpec("upload_images", "上传正文图片", external="微信 API"),
    StepSpec("create_draft", "创建草稿", external="微信 API"),
]

_IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


class WeChatHeadline(BaseModel):
    title: str
    digest: str

    @field_validator("title")
    @classmethod
    def _fit_title(cls, value: str) -> str:
        value = value.strip().strip("《》\"'“”")
        if not value:
            raise ValueError("title is empty")
        return fit_wechat_length(value, TITLE_LIMIT)

    @field_validator("digest")
    @classmethod
    def _fit_digest(cls, value: str) -> str:
        return fit_wechat_length(value, DIGEST_LIMIT)


class WeChatPackage(BaseModel):
    slug: str
    title: str
    digest: str = ""
    author: str | None = None
    source_title: str = ""
    cover_source: Literal["generated", "uploaded"] = "generated"
    cover_figure: str | None = None
    summary_sha256: str = ""
    image_count: int = 0
    formula_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    prepared_at: str
    published_at: str | None = None
    draft_media_id: str | None = None
    thumb_media_id: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wechat_dir(settings: Settings, slug: str) -> Path:
    return settings.resolved_artifacts_dir() / validate_slug(slug) / WECHAT_DIRNAME


def load_package(settings: Settings, slug: str) -> WeChatPackage | None:
    path = wechat_dir(settings, slug) / PACKAGE_FILE
    if not path.is_file():
        return None
    return WeChatPackage.model_validate_json(path.read_text(encoding="utf-8"))


def save_package(settings: Settings, package: WeChatPackage) -> None:
    directory = wechat_dir(settings, package.slug)
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f"{PACKAGE_FILE}.tmp"
    tmp.write_text(package.model_dump_json(indent=2) + "\n", encoding="utf-8")
    tmp.replace(directory / PACKAGE_FILE)


def summary_sha256(settings: Settings, slug: str) -> str:
    path = settings.resolved_artifacts_dir() / slug / "summary.md"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def strip_appendix(markdown_text: str) -> str:
    """Drop the deterministic knowledge-base appendix sections from summary.md."""
    pattern = re.compile(r"^##\s+(" + "|".join(map(re.escape, APPENDIX_HEADINGS)) + r")\s*$", re.MULTILINE)
    match = pattern.search(markdown_text)
    body = markdown_text[: match.start()] if match else markdown_text
    return re.sub(r"\n-{3,}\s*$", "", body.rstrip()).rstrip() + "\n"


def cjk_char_count(text: str) -> int:
    """Count CJK characters; used as the WeChat body length budget."""
    return len(_CJK_RE.findall(text or ""))


def strip_formulas(markdown_text: str) -> str:
    """Remove display/inline LaTeX so WeChat body never depends on formula images."""
    text = _DISPLAY_MATH_RE.sub("", markdown_text)
    text = _INLINE_MATH_RE.sub(lambda match: match.group(1).replace("\\", ""), text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def _strip_outer_fence(content: str) -> str:
    match = re.fullmatch(r"```(?:markdown|md)?\s*(.*?)```", content.strip(), flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else content.strip()


def adapt_article_for_wechat(
    settings: Settings,
    llm: LLMClient,
    *,
    article: str,
    title: str,
) -> str:
    """Rewrite ``summary.md`` into a ~3000-char, formula-free WeChat Markdown body."""
    prompt_path = resolve_prompt_path(settings.resolved_prompts_dir(), settings.wechat_article_prompt_path)
    prompt_vars = load_prompt_module(prompt_path)
    target = max(settings.wechat_article_target_chars, 1000)
    system = prompt_vars["wechat_article_system_prompt"].strip().replace("3000", str(target))
    user = (
        prompt_vars["wechat_article_user_prompt"]
        .replace("{PAPER_TITLE}", title)
        .replace("{ARTICLE}", article)
    )
    rewritten = _strip_outer_fence(llm.complete(system, user))
    rewritten = strip_formulas(rewritten)
    if not rewritten.strip():
        raise PublishingError("公众号正文改写结果为空")
    return rewritten if rewritten.endswith("\n") else rewritten + "\n"


def _read_meta(artifact_dir: Path) -> PaperAssetMeta:
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file():
        return PaperAssetMeta()
    return AssetsManifest.model_validate_json(manifest_path.read_text(encoding="utf-8")).paper


def _people(settings: Settings, slug: str, meta: PaperAssetMeta) -> tuple[list[str], list[str]]:
    """Authors and affiliations for the info card.

    Manifests written before affiliations were parsed (or with the old first-line-only
    author parser) are completed read-only from raw LaTeX; human-edited author lists
    that are not a prefix of the raw list are kept as-is.
    """
    authors, affiliations = list(meta.authors), list(meta.affiliations)
    raw_dir = settings.resolved_raw_dir() / slug
    if affiliations or not raw_dir.is_dir():
        return authors, affiliations
    try:
        from paper_wiki.ingestion.latex_parser import LaTeXParser

        raw_authors, raw_affiliations = LaTeXParser().extract_people(raw_dir)
    except Exception as exc:  # raw tree without a parsable .tex entry
        logger.info("无法从 raw 补全作者单位：slug=%s, %s", slug, exc)
        return authors, affiliations
    if raw_authors and authors == raw_authors[: len(authors)]:
        authors = raw_authors
    return authors, raw_affiliations


def _meta_line(meta: PaperAssetMeta) -> str:
    parts = [", ".join(meta.authors[:6]), meta.venue, str(meta.year or ""), f"arXiv:{meta.arxiv_id}" if meta.arxiv_id else ""]
    return " | ".join(part for part in parts if part)


def _fallback_headline(meta: PaperAssetMeta, article: str, slug: str) -> WeChatHeadline:
    paragraphs = [
        line.strip("> ").strip()
        for line in article.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "!", "|", "-", "$"))
    ]
    digest = re.sub(r"[*`$]", "", paragraphs[0]) if paragraphs else meta.abstract
    digest = re.sub(r"^(一句话导读|核心主张|导读|TL;?DR)\s*[:：]\s*", "", digest, flags=re.IGNORECASE)
    return WeChatHeadline(title=meta.title or slug, digest=digest or meta.title or slug)


def generate_headline(
    settings: Settings,
    llm: LLMClient,
    *,
    article: str,
    meta: PaperAssetMeta,
    slug: str,
) -> WeChatHeadline:
    prompt_path = resolve_prompt_path(settings.resolved_prompts_dir(), settings.wechat_headline_prompt_path)
    prompt_vars = load_prompt_module(prompt_path)
    user = (
        prompt_vars["wechat_headline_user_prompt"]
        .replace("{PAPER_TITLE}", meta.title or slug)
        .replace("{PAPER_META}", _meta_line(meta) or "未知")
        .replace("{ARTICLE}", article[:12000])
    )
    return llm.complete_json(prompt_vars["wechat_headline_system_prompt"].strip(), user, WeChatHeadline)


def _encode_for_wechat(source: Path, target: Path) -> Path:
    """Re-encode an image as RGB JPEG within WeChat's 1MB article-image limit."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".pdf":
        from paper_wiki.ingestion.summary_figure_converter import convert_pdf_first_page_to_jpg

        rendered = target.with_suffix(".src.jpg")
        convert_pdf_first_page_to_jpg(source, rendered)
        source = rendered
    with Image.open(source) as raw:
        image = raw.convert("RGBA") if raw.mode in {"RGBA", "LA", "P"} else raw.convert("RGB")
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    if image.width > MAX_IMAGE_WIDTH:
        ratio = MAX_IMAGE_WIDTH / image.width
        image = image.resize((MAX_IMAGE_WIDTH, max(1, int(image.height * ratio))), Image.LANCZOS)
    target = target.with_suffix(".jpg")
    for quality in (90, 82, 74, 66, 58, 50):
        image.save(target, format="JPEG", quality=quality, optimize=True)
        if target.stat().st_size <= MAX_IMAGE_BYTES:
            break
    else:
        while target.stat().st_size > MAX_IMAGE_BYTES and image.width > 400:
            image = image.resize((int(image.width * 0.8), int(image.height * 0.8)), Image.LANCZOS)
            image.save(target, format="JPEG", quality=60, optimize=True)
    if source.name.endswith(".src.jpg"):
        source.unlink(missing_ok=True)
    return target


def _localize_images(
    article: str, artifact_dir: Path, out_dir: Path, warnings: list[str]
) -> tuple[str, list[str], str | None]:
    """Copy referenced figures into wechat/images and rewrite links.

    Returns ``(markdown, image paths, method figure)``; the method/framework figure, when
    recognised, is listed first and is used both as cover source and as the lead figure.
    """
    images_dir = out_dir / "images"
    copied: dict[str, str] = {}
    order: list[str] = []
    labels: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        alt, raw = match.group(1), match.group(2).strip()
        if raw.startswith(("http://", "https://")):
            return match.group(0)
        source = (artifact_dir / raw.lstrip("./")).resolve()
        try:
            source.relative_to(artifact_dir.resolve())
        except ValueError:
            warnings.append(f"已忽略目录外的图片：{raw}")
            return ""
        if not source.is_file():
            warnings.append(f"图片不存在，已从正文移除：{raw}")
            return ""
        if raw not in copied:
            stem = f"{len(copied) + 1:02d}_{re.sub(r'[^A-Za-z0-9_-]+', '_', source.stem)[:40]}"
            try:
                target = _encode_for_wechat(source, images_dir / stem)
            except Exception as exc:  # unreadable / unsupported image
                warnings.append(f"图片无法处理，已从正文移除：{raw}（{exc}）")
                return ""
            copied[raw] = target.relative_to(out_dir).as_posix()
            order.append(copied[raw])
            caption_line = re.match(r"[ \t]*\n(?:[ \t]*\n)?\*{1,2}(图[^\n]*)", article[match.end():])
            labels[copied[raw]] = f"{alt} {caption_line.group(1) if caption_line else ''} {source.stem}"
            progress.detail(f"已处理 {len(copied)} 张图片")
        return f"![{alt}]({copied[raw]})"

    rewritten = _IMAGE_LINK_RE.sub(repl, article)
    # Method overview figures make the most recognisable cover; move one to the front.
    preferred = next((path for path in order if _COVER_HINT_RE.search(labels.get(path, ""))), None)
    if preferred:
        order = [preferred, *[path for path in order if path != preferred]]
    return rewritten, order, preferred


def lead_figure_caption(article: str, path: str) -> str | None:
    """Return the caption of the method figure at ``path``; leave the body figure in place.

    The same figure is also rendered at the top of the WeChat article, so the method
    section keeps its illustration. Returns ``None`` when ``path`` is not in the body.
    """
    pattern = re.compile(
        rf"^!\[([^\]]*)\]\({re.escape(path)}\)[ \t]*(?:\n(?:[ \t]*\n)?\*{{1,2}}图\s*\d*\s*[:：]\s*(.+?)\*{{1,2}}[ \t]*)?$",
        re.MULTILINE,
    )
    match = pattern.search(article)
    if not match:
        return None
    alt, caption = match.group(1), match.group(2)
    return (caption or alt).strip()


def _info_card_markdown(
    *,
    title: str,
    authors: list[str],
    affiliations: list[str],
    venue: str | None,
    year: int | None,
    arxiv_id: str | None,
) -> str:
    """Plain Markdown for the paper info block; Cursor / gzh-design styles it."""
    lines = [f"**标题**：{title}"]
    if authors:
        lines.append(f"**作者**：{'，'.join(authors)}")
    if affiliations:
        lines.append("**单位**：")
        lines.extend(f"{index}. {name}" for index, name in enumerate(affiliations[:8], start=1))
    source_parts = [part for part in [venue, str(year or ""), f"arXiv:{arxiv_id}" if arxiv_id else ""] if part]
    if source_parts:
        lines.append(f"**来源**：{' · '.join(source_parts)}")
    return "\n".join(lines) + "\n"


def _prepend_lead_and_info(
    article: str,
    *,
    method_figure: str | None,
    lead_caption: str | None,
    title: str,
    authors: list[str],
    affiliations: list[str],
    venue: str | None,
    year: int | None,
    arxiv_id: str | None,
) -> str:
    """Insert the lead method figure and paper info card after the H1 title."""
    blocks: list[str] = []
    if method_figure:
        blocks.append(f"![{lead_caption or ''}]({method_figure})")
    blocks.append(
        _info_card_markdown(
            title=title,
            authors=authors,
            affiliations=affiliations,
            venue=venue,
            year=year,
            arxiv_id=arxiv_id,
        ).rstrip()
    )
    insert = "\n\n".join(blocks) + "\n\n"
    match = re.match(r"^(#[^\n]*\n+)", article)
    if match:
        return match.group(1) + insert + article[match.end() :]
    return insert + article


_COVER_HINT_RE = re.compile(
    r"framework|overview|pipeline|architecture|method|\bmodel\b|框架|总览|概览|流程|整体|架构", re.IGNORECASE
)


def _make_cover(package: WeChatPackage, meta: PaperAssetMeta, out_dir: Path) -> None:
    """Prefer a full-bleed method-figure cover; fall back to the branded title card."""
    subtitle = " | ".join(part for part in [meta.venue, str(meta.year or ""), f"arXiv {meta.arxiv_id}" if meta.arxiv_id else ""] if part)
    figure = out_dir / package.cover_figure if package.cover_figure else None
    if figure is not None and not figure.is_file():
        figure = None
    generate_wechat_cover(package.title, out_dir / COVER_FILE, subtitle=subtitle, figure_path=figure)


def prepare_paper_wechat(
    settings: Settings,
    slug: str,
    *,
    title: str | None = None,
    digest: str | None = None,
    author: str | None = None,
    regenerate_headline: bool = True,
    llm: LLMClient | None = None,
) -> WeChatPackage:
    """Build the publishable package for ``artifacts/{slug}/summary.md``."""
    slug = validate_slug(slug)
    artifact_dir = settings.resolved_artifacts_dir() / slug
    out_dir = artifact_dir / WECHAT_DIRNAME
    progress.plan(PREPARE_STEPS)
    previous = load_package(settings, slug)
    warnings: list[str] = []

    client = llm or build_llm_client(settings)
    with progress.step("read"):
        summary_path = artifact_dir / "summary.md"
        if not summary_path.is_file():
            raise PublishingError(f"{slug} 还没有 summary.md，请先生成精读笔记")
        full_article = summary_path.read_text(encoding="utf-8")
        # Headline generation only needs the reading note; adapt keeps the appendix.
        note_for_headline = strip_appendix(full_article)
        meta = _read_meta(artifact_dir)
        current_hash = summary_sha256(settings, slug)

    keep_previous = previous is not None and not regenerate_headline
    if title and digest:
        progress.skip("headline", "使用手动填写的标题与摘要")
        headline = WeChatHeadline(title=title, digest=digest)
    elif keep_previous:
        assert previous is not None
        progress.skip("headline", "沿用上次的标题与摘要")
        headline = WeChatHeadline(title=title or previous.title, digest=digest or previous.digest or previous.title)
    else:
        with progress.step("headline"):
            try:
                generated = generate_headline(settings, client, article=note_for_headline, meta=meta, slug=slug)
            except Exception as exc:
                logger.warning("生成公众号标题失败，回退到论文标题：%s", exc)
                warnings.append(f"标题/摘要生成失败，已回退到论文标题：{exc}")
                progress.detail("LLM 调用失败，已回退到论文标题和开头段落")
                generated = _fallback_headline(meta, note_for_headline, slug)
            headline = WeChatHeadline(title=title or generated.title, digest=digest or generated.digest)

    source_path = out_dir / SOURCE_FILE
    with progress.step("adapt"):
        # summary.md is already the WeChat-ready blog (v5: ~5 min, no formulas);
        # only strip residual LaTeX as a safety net, then hand off to Cursor layout.
        article = strip_formulas(full_article)
        chars = cjk_char_count(article)
        progress.detail(f"直接使用 summary.md（已去公式），约 {chars} 字")
        out_dir.mkdir(parents=True, exist_ok=True)

    with progress.step("images"):
        for name in ("images", "formulas"):
            shutil.rmtree(out_dir / name, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        article, images, method_figure = _localize_images(article, artifact_dir, out_dir, warnings)
        lead_caption = lead_figure_caption(article, method_figure) if method_figure else None
        if method_figure and lead_caption is None:
            lead_caption = ""
        authors, affiliations = _people(settings, slug, meta)
        article = _prepend_lead_and_info(
            article,
            method_figure=method_figure,
            lead_caption=lead_caption,
            title=meta.title or slug,
            authors=authors,
            affiliations=affiliations,
            venue=meta.venue,
            year=meta.year,
            arxiv_id=meta.arxiv_id,
        )
        source_path.write_text(article, encoding="utf-8")

    with progress.step("render"):
        try:
            html_path = render_markdown_html(
                source_path,
                settings,
                preferred_name=ARTICLE_FILE,
            )
        except CursorRenderError as exc:
            raise PublishingError(f"Cursor 排版失败：{exc}") from exc
        html = sanitize_wechat_blog_html(html_path.read_text(encoding="utf-8"))
        validate_wechat_html(html)
        (out_dir / ARTICLE_FILE).write_text(html, encoding="utf-8")
        formula_count = len(set(re.findall(r'src="(formulas/[^"]+)"', html)))
        if formula_count:
            warnings.append(f"正文仍含 {formula_count} 个公式图片，建议检查 summary.md")
        progress.detail(f"已写入 {ARTICLE_FILE}")

    package = WeChatPackage(
        slug=slug,
        title=headline.title,
        digest=headline.digest,
        author=fit_wechat_length(author, AUTHOR_LIMIT) if author else (previous.author if previous else None),
        source_title=meta.title,
        cover_source=previous.cover_source if previous and (out_dir / COVER_FILE).is_file() else "generated",
        cover_figure=images[0] if images else None,
        summary_sha256=current_hash,
        image_count=len(images),
        formula_count=formula_count,
        warnings=warnings,
        prepared_at=_now(),
    )

    with progress.step("cover"):
        if package.cover_source == "uploaded":
            progress.detail("保留已上传的自定义封面")
        else:
            _make_cover(package, meta, out_dir)

    save_package(settings, package)
    logger.info("公众号发布包已生成：slug=%s, images=%d, formulas=%d", slug, len(images), formula_count)
    return package


def update_package_fields(
    settings: Settings,
    slug: str,
    *,
    title: str | None = None,
    digest: str | None = None,
    author: str | None = None,
) -> WeChatPackage:
    """Apply manual edits; title-card covers are redrawn when the title changes."""
    package = load_package(settings, slug)
    if package is None:
        raise PublishingError("请先生成公众号预览")
    changes: dict[str, object] = {}
    if title is not None:
        changes["title"] = WeChatHeadline(title=title, digest="x").title
    if digest is not None:
        changes["digest"] = fit_wechat_length(digest, DIGEST_LIMIT)
    if author is not None:
        changes["author"] = fit_wechat_length(author, AUTHOR_LIMIT) or None
    updated = package.model_copy(update=changes)
    # Method-figure covers do not embed the title, so skip redrawing them.
    if (
        "title" in changes
        and changes["title"] != package.title
        and package.cover_source == "generated"
        and not package.cover_figure
    ):
        _make_cover(updated, _read_meta(settings.resolved_artifacts_dir() / slug), wechat_dir(settings, slug))
    save_package(settings, updated)
    return updated


def set_custom_cover(settings: Settings, slug: str, filename: str, content: bytes) -> WeChatPackage:
    package = load_package(settings, slug)
    if package is None:
        raise PublishingError("请先生成公众号预览")
    if Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("封面图只支持 JPG 或 PNG")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("封面图不能超过 10MB")
    out_dir = wechat_dir(settings, slug)
    tmp = out_dir / f"upload{Path(filename).suffix.lower()}"
    tmp.write_bytes(content)
    try:
        with Image.open(tmp) as raw:
            raw.convert("RGB").save(out_dir / COVER_FILE, format="JPEG", quality=92, optimize=True)
    except OSError as exc:
        raise ValueError("无法读取封面图片") from exc
    finally:
        tmp.unlink(missing_ok=True)
    updated = package.model_copy(update={"cover_source": "uploaded"})
    save_package(settings, updated)
    return updated


def reset_cover(settings: Settings, slug: str) -> WeChatPackage:
    package = load_package(settings, slug)
    if package is None:
        raise PublishingError("请先生成公众号预览")
    updated = package.model_copy(update={"cover_source": "generated"})
    _make_cover(updated, _read_meta(settings.resolved_artifacts_dir() / slug), wechat_dir(settings, slug))
    save_package(settings, updated)
    return updated


def publish_paper_wechat(
    settings: Settings,
    slug: str,
    *,
    client: WeChatClient | None = None,
) -> WeChatPackage:
    """Upload cover + images and create the draft from a prepared package."""
    package = load_package(settings, slug)
    if package is None:
        raise PublishingError("请先生成公众号预览")
    if not settings.wechat_appid or not settings.wechat_secret:
        raise WeChatConfigError("缺少公众号凭证：请在 .env 中配置 WECHAT_APPID 和 WECHAT_SECRET")
    out_dir = wechat_dir(settings, slug)
    html_path = out_dir / ARTICLE_FILE
    progress.plan(PUBLISH_STEPS)
    wechat = client or WeChatClient(
        settings.wechat_appid,
        settings.wechat_secret,
        timeout=settings.wechat_request_timeout_seconds,
        proxy=settings.wechat_proxy,
    )

    with progress.step("upload_cover"):
        thumb_media_id = wechat.upload_permanent_image(out_dir / COVER_FILE)

    with progress.step("upload_images"):
        total = len(set(re.findall(r'<img[^>]+src="(?!https?://)([^"]+)"', html_path.read_text(encoding="utf-8"))))
        done = 0

        def upload(path: Path) -> str:
            nonlocal done
            url = wechat.upload_article_image(path)
            done += 1
            progress.detail(f"{done}/{total}")
            return url

        processed = replace_local_images(html_path.read_text(encoding="utf-8"), html_file=html_path, upload_image=upload)

    with progress.step("create_draft"):
        payload = wechat.create_draft(
            title=package.title,
            content=processed.content,
            thumb_media_id=thumb_media_id,
            author=package.author or (fit_wechat_length(settings.wechat_author, AUTHOR_LIMIT) if settings.wechat_author else None),
            digest=package.digest or None,
        )

    updated = package.model_copy(
        update={
            "draft_media_id": str(payload["media_id"]),
            "thumb_media_id": thumb_media_id,
            "published_at": _now(),
        }
    )
    save_package(settings, updated)
    (out_dir / "article_wechat_rendered.html").write_text(processed.content, encoding="utf-8")
    logger.info("公众号草稿已创建：slug=%s, media_id=%s", slug, updated.draft_media_id)
    return updated


def preview_html(settings: Settings, slug: str, *, file_url_prefix: str) -> str:
    """Article HTML with relative image paths pointed at the artifact file endpoint."""
    html = (wechat_dir(settings, slug) / ARTICLE_FILE).read_text(encoding="utf-8")
    return re.sub(
        r'(<img[^>]+src=")(?!https?://)([^"]+)"',
        lambda m: f'{m.group(1)}{file_url_prefix}{WECHAT_DIRNAME}/{m.group(2)}"',
        html,
    )


def package_to_dict(package: WeChatPackage, settings: Settings) -> dict[str, object]:
    current_hash = summary_sha256(settings, package.slug)
    return {
        **json.loads(package.model_dump_json()),
        "stale": bool(package.summary_sha256 and current_hash and current_hash != package.summary_sha256),
    }
