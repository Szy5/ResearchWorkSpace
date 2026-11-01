"""Generate WeChat cover images: title on the left, optional key figure on the right."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from paper_wiki.publishing.wechat_limits import TITLE_LIMIT, fit_wechat_length

# WeChat shows the first article's cover at roughly 2.35:1; render at 2x for sharpness.
COVER_WIDTH = 1800
COVER_HEIGHT = 766

_BG_TOP = (6, 78, 59)  # #064E3B
_BG_BOTTOM = (5, 150, 105)  # #059669
_ACCENT = (167, 243, 208)  # #A7F3D0
_TEXT = (255, 255, 255)
_MUTED = (209, 250, 229)

# (path, has_latin_glyphs). DroidSansFallback only covers CJK, so Latin runs
# fall back to a separate font.
_CJK_FONT_CANDIDATES = (
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"), True),
    (Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"), True),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), True),
    (Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"), True),
    (Path("/System/Library/Fonts/PingFang.ttc"), True),
    (Path("C:/Windows/Fonts/msyh.ttc"), True),
    (Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"), False),
)
_LATIN_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
)


def default_wechat_title(raw: str | None, *, fallback: str = "Paper-Wiki") -> str:
    """Normalize a draft title for WeChat (non-empty, within the editor title limit)."""
    title = " ".join((raw or "").split()).strip() or fallback
    return fit_wechat_length(title, TITLE_LIMIT)


def _truetype(path: Path, size: int) -> ImageFont.FreeTypeFont | None:
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return None


class _MixedFont:
    """CJK font plus a Latin fallback, drawn run by run."""

    def __init__(self, size: int) -> None:
        self.cjk: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
        self.latin: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
        for path, has_latin in _CJK_FONT_CANDIDATES:
            if path.exists() and (font := _truetype(path, size)):
                self.cjk = font
                if has_latin:
                    self.latin = font
                break
        if self.latin is None:
            self.latin = next(
                (font for path in _LATIN_FONT_CANDIDATES if path.exists() and (font := _truetype(path, size))),
                None,
            )
        fallback = ImageFont.load_default()
        self.cjk = self.cjk or self.latin or fallback
        self.latin = self.latin or self.cjk

    def runs(self, text: str) -> list[tuple[str, ImageFont.ImageFont]]:
        runs: list[tuple[str, ImageFont.ImageFont]] = []
        for char in text:
            font = self.latin if ord(char) < 0x2000 else self.cjk
            if runs and runs[-1][1] is font:
                runs[-1] = (runs[-1][0] + char, font)
            else:
                runs.append((char, font))
        return runs

    def draw(self, draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, *, fill, **kwargs) -> None:
        x, y = xy
        for chunk, font in self.runs(text):
            draw.text((x, y), chunk, fill=fill, font=font, **kwargs)
            x += draw.textlength(chunk, font=font)


def _load_font(size: int) -> _MixedFont:
    return _MixedFont(size)


def _measure(draw: ImageDraw.ImageDraw, text: str, font: _MixedFont) -> tuple[float, float]:
    width = sum(draw.textlength(chunk, font=f) for chunk, f in font.runs(text))
    height = max((float(draw.textbbox((0, 0), chunk, font=f)[3]) for chunk, f in font.runs(text)), default=0.0)
    return width, height


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: _MixedFont,
    max_width: float,
    *,
    max_lines: int = 3,
) -> list[str]:
    """Greedy wrap that keeps Latin words intact and breaks CJK anywhere."""
    tokens: list[str] = []
    buffer = ""
    for char in text:
        if char.isascii() and not char.isspace():
            buffer += char
            continue
        if buffer:
            tokens.append(buffer)
            buffer = ""
        tokens.append(char)
    if buffer:
        tokens.append(buffer)

    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = current + token
        if _measure(draw, candidate.strip(), font)[0] <= max_width or not current.strip():
            current = candidate
            continue
        lines.append(current.strip())
        current = token.lstrip()
    if current.strip():
        lines.append(current.strip())

    if len(lines) > max_lines:
        kept = lines[:max_lines]
        last = kept[-1]
        while last and _measure(draw, last + "…", font)[0] > max_width:
            last = last[:-1]
        kept[-1] = last.rstrip() + "…"
        return kept
    return lines or [text]


def _gradient(width: int, height: int) -> Image.Image:
    base = Image.new("RGB", (width, height), _BG_TOP)
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(_BG_TOP, _BG_BOTTOM))
        draw.line([(0, y), (width, y)], fill=color)
    return base


def _paste_figure(canvas: Image.Image, figure_path: Path, box: tuple[int, int, int, int]) -> bool:
    try:
        with Image.open(figure_path) as raw:
            figure = raw.convert("RGBA")
    except OSError:
        return False
    left, top, right, bottom = box
    padding = 28
    card = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=28, fill=255)
    white = Image.new("RGBA", card.size, (255, 255, 255, 255))
    card.paste(white, (0, 0), mask)

    max_w, max_h = card.width - padding * 2, card.height - padding * 2
    scale = min(max_w / figure.width, max_h / figure.height)
    resized = figure.resize((max(1, int(figure.width * scale)), max(1, int(figure.height * scale))), Image.LANCZOS)
    offset = ((card.width - resized.width) // 2, (card.height - resized.height) // 2)
    card.paste(resized, offset, resized)
    canvas.paste(card, (left, top), card)
    return True


def cover_from_figure(
    figure_path: Path,
    output_path: Path,
    *,
    width: int = COVER_WIDTH,
    height: int = COVER_HEIGHT,
) -> Path | None:
    """Make a full-bleed WeChat cover from a method figure; return ``None`` if unreadable."""
    try:
        with Image.open(figure_path) as raw:
            figure = raw.convert("RGB")
    except OSError:
        return None
    scale = max(width / figure.width, height / figure.height)
    resized = figure.resize(
        (max(1, int(figure.width * scale)), max(1, int(figure.height * scale))),
        Image.LANCZOS,
    )
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    cover = resized.crop((left, top, left + width, top + height))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cover.save(output_path, format="JPEG", quality=90, optimize=True)
    return output_path


def generate_wechat_cover(
    title: str,
    output_path: Path,
    *,
    brand: str = "Paper-Wiki",
    kicker: str = "",
    subtitle: str = "",
    figure_path: Path | None = None,
    width: int = COVER_WIDTH,
    height: int = COVER_HEIGHT,
) -> Path:
    """Write a JPEG cover and return its path.

    When ``figure_path`` points to a readable method figure, the cover is that
    figure alone (full-bleed crop). Otherwise fall back to the branded title card.
    """
    if figure_path is not None and Path(figure_path).is_file():
        written = cover_from_figure(Path(figure_path), output_path, width=width, height=height)
        if written is not None:
            return written

    display_title = default_wechat_title(title)
    canvas = _gradient(width, height).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    margin_x = int(width * 0.06)
    # Decorative rings keep the right side from looking empty when no figure is available.
    for radius, alpha in ((int(height * 0.62), 40), (int(height * 0.42), 60)):
        cx, cy = int(width * 0.86), int(height * 0.5)
        ring = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(*_ACCENT, alpha), width=10)
        canvas.alpha_composite(ring)
    draw = ImageDraw.Draw(canvas)

    text_right = int(width * 0.78)
    max_text_width = text_right - margin_x

    title_size = int(height * (0.12 if len(display_title) <= 14 else 0.1))
    title_font = _load_font(title_size)
    lines = _wrap_lines(draw, display_title, title_font, max_text_width)
    line_height = _measure(draw, "测Ag", title_font)[1] * 1.35
    top = int(height * 0.14)
    if kicker:
        kicker_font = _load_font(int(height * 0.055))
        kicker_w, kicker_h = _measure(draw, kicker, kicker_font)
        pill_pad_x, pill_pad_y = 22, 12
        draw.rounded_rectangle(
            (margin_x, top, margin_x + kicker_w + pill_pad_x * 2, top + kicker_h + pill_pad_y * 2 + 8),
            radius=int((kicker_h + pill_pad_y * 2) / 2),
            fill=_ACCENT,
        )
        kicker_font.draw(draw, (margin_x + pill_pad_x, top + pill_pad_y), kicker, fill=_BG_TOP)
        y = top + kicker_h + pill_pad_y * 2 + int(height * 0.08)
    else:
        block = line_height * len(lines) + (height * 0.08 if subtitle else 0)
        y = max(top, int((height * 0.9 - block) / 2))
    for line in lines:
        title_font.draw(draw, (margin_x, y), line, fill=_TEXT, stroke_width=1, stroke_fill=_TEXT)
        y += line_height

    small_font = _load_font(int(height * 0.045))
    if subtitle:
        sub = subtitle
        while sub and _measure(draw, sub, small_font)[0] > max_text_width:
            sub = sub[:-1]
        small_font.draw(draw, (margin_x, y + int(height * 0.03)), sub if sub == subtitle else sub.rstrip() + "…", fill=_MUTED)

    _, brand_h = _measure(draw, brand, small_font)
    small_font.draw(draw, (margin_x, height - int(height * 0.1) - brand_h), brand, fill=_MUTED)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="JPEG", quality=90, optimize=True)
    return output_path
