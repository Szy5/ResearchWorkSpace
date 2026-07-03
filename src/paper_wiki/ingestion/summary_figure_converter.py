from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)

MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
DEFAULT_RENDER_ZOOM = 2.0
DEFAULT_JPEG_QUALITY = 85


@dataclass
class FigureConversionResult:
    """summary.md 中 PDF 图转 JPG 的执行结果。"""

    converted: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def convert_summary_pdf_figures(
    summary_path: Path,
    *,
    slug: str,
    raw_dir: Path,
    artifact_dir: Path,
) -> FigureConversionResult:
    """
    扫描 summary.md 中的 PDF 图片引用，转换为 JPG 并回写相对路径。

    JPG 输出到 artifacts/{slug}/figures/，Markdown 引用改为 figures/{name}.jpg。
    """
    content = summary_path.read_text(encoding="utf-8")
    result = FigureConversionResult()
    output_dir = artifact_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    def repl(match: re.Match[str]) -> str:
        alt, image_ref = match.group(1), match.group(2).strip()
        if not image_ref.lower().endswith(".pdf"):
            return match.group(0)

        pdf_path = resolve_source_pdf(
            image_ref,
            slug=slug,
            raw_dir=raw_dir,
            summary_path=summary_path,
        )
        if pdf_path is None:
            result.skipped.append((image_ref, "source pdf not found"))
            logger.warning("未找到 PDF 图源：ref=%s, slug=%s", image_ref, slug)
            return match.group(0)

        jpg_name = f"{pdf_path.stem}.jpg"
        jpg_path = output_dir / jpg_name
        jpg_ref = f"figures/{jpg_name}"

        try:
            convert_pdf_first_page_to_jpg(pdf_path, jpg_path)
        except Exception as exc:
            result.skipped.append((image_ref, str(exc)))
            logger.warning("PDF 转 JPG 失败：pdf=%s, error=%s", pdf_path, exc)
            return match.group(0)

        result.converted.append((image_ref, jpg_ref))
        logger.info("已转换图片：%s -> %s", pdf_path.name, jpg_path)
        return f"![{alt}]({jpg_ref})"

    updated = MARKDOWN_IMAGE_RE.sub(repl, content)
    if updated != content:
        summary_path.write_text(updated, encoding="utf-8")
    return result


def resolve_source_pdf(
    image_ref: str,
    *,
    slug: str,
    raw_dir: Path,
    summary_path: Path,
) -> Path | None:
    """把 Markdown 中的图片引用解析为 raw 目录下的 PDF 绝对路径。"""
    if image_ref.startswith(("http://", "https://")):
        return None

    ref_path = Path(image_ref)
    paper_dir = raw_dir / slug

    from_summary = (summary_path.parent / ref_path).resolve()
    if from_summary.is_file() and from_summary.suffix.lower() == ".pdf":
        return from_summary

    exact = (paper_dir / ref_path).resolve()
    if exact.is_file() and exact.suffix.lower() == ".pdf":
        return exact

    case_resolved = find_file_case_insensitive(paper_dir, ref_path)
    if case_resolved is not None and case_resolved.suffix.lower() == ".pdf":
        return case_resolved

    return None


def find_file_case_insensitive(base_dir: Path, relative: Path) -> Path | None:
    """在 base_dir 下按路径逐段大小写不敏感查找文件。"""
    current = base_dir
    for part in relative.parts:
        if not current.exists():
            return None
        if part in {".", ""}:
            continue
        matches = [p for p in current.iterdir() if p.name.lower() == part.lower()]
        if not matches:
            return None
        current = matches[0]
    return current if current.is_file() else None


def convert_pdf_first_page_to_jpg(
    pdf_path: Path,
    jpg_path: Path,
    *,
    zoom: float = DEFAULT_RENDER_ZOOM,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> None:
    """将 PDF 第一页渲染为 JPG。"""
    jpg_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        if doc.page_count == 0:
            raise ValueError(f"PDF has no pages: {pdf_path}")
        page = doc.load_page(0)
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        pixmap.save(jpg_path, output="jpeg", jpg_quality=quality)
