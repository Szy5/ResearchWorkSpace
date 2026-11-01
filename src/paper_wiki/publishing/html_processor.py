from __future__ import annotations

from collections.abc import Callable
from html import escape
from pathlib import Path
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from paper_wiki.publishing.exceptions import HTMLValidationError
from paper_wiki.publishing.models import ProcessedHTML

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
_SCROLL_STYLE_RE = re.compile(r"overflow-x\s*:\s*scroll", re.IGNORECASE)


def sanitize_wechat_blog_html(html: str) -> str:
    """Strip gzh-design extras that do not fit paper-skim WeChat posts.

    Removes the horizontal toc-scroll strip (📦 Highlights/Parts + 👉 滑动) and
    rewrites magazine-style ``PART 01`` chapter headers into the compact
    ``01 章节名`` form used by the deterministic markdown renderer.
    """
    if not html or not html.strip():
        return html
    soup = BeautifulSoup(html, "html.parser")
    _remove_toc_scroll(soup)
    _simplify_part_chapter_titles(soup)
    return str(soup)


def _remove_toc_scroll(soup: BeautifulSoup) -> None:
    victims: list[Tag] = []
    for section in soup.find_all("section"):
        style = section.get("style") or ""
        if not _SCROLL_STYLE_RE.search(style):
            continue
        text = section.get_text(" ", strip=True)
        if "PART" not in text and "Highlights" not in text and "Parts" not in text:
            continue
        parent = section.parent if isinstance(section.parent, Tag) else None
        victims.append(parent if parent is not None and parent.name == "section" else section)
    for node in victims:
        if node.parent is not None:
            node.decompose()


def _simplify_part_chapter_titles(soup: BeautifulSoup) -> None:
    for header in list(soup.find_all("section")):
        style = header.get("style") or ""
        if "display:flex" not in style.replace(" ", "") and "display: flex" not in style:
            continue
        texts = [t.strip() for t in header.stripped_strings if t.strip()]
        if len(texts) < 2 or texts[1] not in {"PART", "LAST"}:
            continue
        number = texts[0]
        title = next((t for t in texts[2:] if t and "·" not in t and not t.isascii()), None)
        if title is None:
            title = next((t for t in texts[2:] if t and t not in {"PART", "LAST"}), None)
        if not number or not title:
            continue
        replacement = BeautifulSoup(
            (
                '<section style="margin:40px 0 20px;display:flex;align-items:baseline;gap:10px;">'
                f'<span style="font-size:22px;font-weight:900;color:#059669;line-height:1;">'
                f'<span leaf="">{escape(number)}</span></span>'
                f'<span style="font-size:18px;font-weight:800;color:#111827;line-height:1.4;">'
                f'<span leaf="">{escape(title)}</span></span>'
                "</section>"
            ),
            "html.parser",
        ).section
        header.replace_with(replacement)


def validate_wechat_html(html: str) -> None:
    """Reject HTML that is clearly unsuitable for the WeChat draft API."""
    if not html or not html.strip():
        raise HTMLValidationError("HTML content is empty")

    soup = BeautifulSoup(html, "html.parser")
    if soup.find("script"):
        raise HTMLValidationError("HTML contains <script>, which is not supported for WeChat publishing")

    if soup.find("link", rel=lambda value: value and "stylesheet" in value):
        raise HTMLValidationError("HTML contains external stylesheet links, which are not supported")


def _is_remote_src(src: str) -> bool:
    parsed = urlparse(src)
    return parsed.scheme in {"http", "https"}


def _resolve_image_path(src: str, html_file: Path) -> Path:
    parsed = urlparse(src)
    if parsed.scheme == "data":
        raise HTMLValidationError("inline data: images are not supported; save the image as a file first")
    if parsed.scheme and parsed.scheme not in {"file"}:
        raise HTMLValidationError(f"unsupported image URL scheme: {parsed.scheme}")

    raw_path = parsed.path if parsed.scheme == "file" else src
    image_path = Path(raw_path)
    if not image_path.is_absolute():
        image_path = html_file.parent / image_path
    image_path = image_path.resolve()

    if not image_path.exists() or not image_path.is_file():
        raise HTMLValidationError(f"local image referenced by HTML does not exist: {src}")
    if image_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        raise HTMLValidationError(f"unsupported local image format for WeChat upload: {image_path}")
    return image_path


def replace_local_images(
    html: str,
    *,
    html_file: Path,
    upload_image: Callable[[Path], str],
) -> ProcessedHTML:
    """Upload local images referenced by HTML and replace src values with returned URLs."""
    validate_wechat_html(html)
    soup = BeautifulSoup(html, "html.parser")
    image_map: dict[str, str] = {}

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        if _is_remote_src(src):
            continue

        image_path = _resolve_image_path(src, html_file)
        image_key = str(image_path)
        if image_key not in image_map:
            image_map[image_key] = upload_image(image_path)
        img["src"] = image_map[image_key]

    return ProcessedHTML(
        content=str(soup),
        uploaded_image_count=len(image_map),
        image_map=image_map,
    )

