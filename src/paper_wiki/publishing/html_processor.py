from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from paper_wiki.publishing.exceptions import HTMLValidationError
from paper_wiki.publishing.models import ProcessedHTML

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}


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

