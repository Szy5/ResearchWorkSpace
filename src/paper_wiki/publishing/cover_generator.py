"""Generate solid-color WeChat cover images with centered title text."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# WeChat cover ratio is roughly 2.35:1; 900x383 is a common upload size.
COVER_WIDTH = 900
COVER_HEIGHT = 383
MAX_TITLE_CHARS = 64

# Cool workspace palette — same family as the web UI cobalt/slate accents.
_PALETTE = (
    (31, 94, 255),  # cobalt
    (15, 118, 110),  # teal
    (30, 58, 95),  # navy
    (51, 65, 85),  # slate
    (14, 116, 144),  # cyan-steel
)

_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def default_wechat_title(raw: str | None, *, fallback: str = "Paper-Wiki") -> str:
    """Normalize a draft title for WeChat (non-empty, length-capped)."""
    title = " ".join((raw or "").split()).strip() or fallback
    if len(title) > MAX_TITLE_CHARS:
        return title[: MAX_TITLE_CHARS - 1].rstrip() + "…"
    return title


def _pick_color(seed: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return _PALETTE[int(digest[:8], 16) % len(_PALETTE)]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[float, float]:
    box = draw.textbbox((0, 0), text, font=font)
    return float(box[2] - box[0]), float(box[3] - box[1])


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: float,
    *,
    max_lines: int = 4,
) -> list[str]:
    if not text:
        return [""]

    lines: list[str] = []
    remaining = text
    while remaining and len(lines) < max_lines:
        if _measure(draw, remaining, font)[0] <= max_width:
            lines.append(remaining)
            remaining = ""
            break

        # Prefer wrapping on spaces for Latin; otherwise bisect by character (CJK).
        split_at = None
        for index in range(len(remaining), 0, -1):
            chunk = remaining[:index]
            if _measure(draw, chunk, font)[0] <= max_width:
                space = chunk.rfind(" ")
                split_at = space if space >= max(8, index // 3) else index
                break
        if split_at is None or split_at <= 0:
            split_at = max(1, len(remaining) // 2)

        if len(lines) == max_lines - 1 and remaining[split_at:]:
            chunk = remaining[:split_at].rstrip()
            while chunk and _measure(draw, chunk + "…", font)[0] > max_width:
                chunk = chunk[:-1]
            lines.append((chunk or remaining[:1]) + "…")
            remaining = ""
            break

        lines.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    return lines or [text[:12] + "…"]


def generate_wechat_cover(
    title: str,
    output_path: Path,
    *,
    brand: str = "Paper-Wiki",
    width: int = COVER_WIDTH,
    height: int = COVER_HEIGHT,
) -> Path:
    """Write a solid-background JPEG cover with title text; return the path."""
    display_title = default_wechat_title(title)
    background = _pick_color(display_title)
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    # Soft left edge accent bar for a consistent pipeline look.
    accent = tuple(min(255, channel + 28) for channel in background)
    draw.rectangle((0, 0, 14, height), fill=accent)

    title_font = _load_font(44 if len(display_title) <= 24 else 36)
    brand_font = _load_font(22)
    padding_x = 56
    max_text_width = width - padding_x * 2
    lines = _wrap_lines(draw, display_title, title_font, max_text_width)

    line_height = _measure(draw, "测Ag", title_font)[1] + 10
    block_height = line_height * len(lines)
    start_y = (height - block_height) / 2 - 8

    for index, line in enumerate(lines):
        line_width, _ = _measure(draw, line, title_font)
        x = (width - line_width) / 2
        y = start_y + index * line_height
        draw.text((x, y), line, fill=(255, 255, 255), font=title_font)

    brand_width, brand_height = _measure(draw, brand, brand_font)
    draw.text(
        ((width - brand_width) / 2, height - brand_height - 28),
        brand,
        fill=(220, 228, 240),
        font=brand_font,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=92, optimize=True)
    return output_path
