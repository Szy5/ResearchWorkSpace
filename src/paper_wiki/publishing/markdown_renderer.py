from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag
import markdown

from paper_wiki.publishing.math_render import formula_fallback_html, latex_to_inline_html, render_formula_png


@dataclass(frozen=True)
class RenderedMarkdown:
    title: str
    html: str


def _safe_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return ""
    return escape(value.strip(), quote=True)


def _safe_image_src(value: str) -> str:
    raw = value.strip()
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return escape(raw, quote=True)
    if parsed.scheme or parsed.netloc:
        return ""
    parts = parsed.path.replace("\\", "/").split("/")
    if parsed.path.startswith("/") or ".." in parts:
        return ""
    return escape(raw, quote=True)


def _inline(node: NavigableString | Tag) -> str:
    if isinstance(node, NavigableString):
        text = str(node)
        return f'<span leaf="">{escape(text)}</span>' if text else ""

    content = "".join(_inline(child) for child in node.children)
    name = node.name.lower()
    if name == "strong":
        return f'<strong style="color:#059669;font-weight:700;">{content}</strong>'
    if name == "em":
        return f'<span style="font-style:italic;color:#4B5563;">{content}</span>'
    if name in {"del", "s", "strike"}:
        return f'<span style="color:#6B7280;text-decoration:line-through;">{content}</span>'
    if name == "code":
        return (
            '<span style="background:#F3F4F6;color:#059669;padding:1px 6px;border-radius:4px;'
            f'font-family:Consolas,Monaco,monospace;font-size:13px;">{content}</span>'
        )
    if name == "a":
        href = _safe_url(str(node.get("href") or ""))
        if not href:
            return content
        return f'<a href="{href}" style="color:#059669;text-decoration:underline;">{content}</a>'
    if name == "br":
        return "<br>"
    if name == "u":
        return f'<span style="border-bottom:2px solid #A7F3D0;font-weight:600;">{content}</span>'
    return content


def _inline_children(node: Tag) -> str:
    return "".join(_inline(child) for child in node.children)


def figure_block(src: str, alt: str = "", *, margin: str = "0") -> str:
    """Framed image with a centred caption; ``margin`` is the CSS margin of the wrapper."""
    src = _safe_image_src(src)
    # Relative local image paths intentionally have no URL scheme and are kept.
    if not src:
        return ""
    alt = escape(alt)
    caption = (
        f'<p style="font-size:12px;color:#9CA3AF;text-align:center;margin:0 0 24px;">'
        f'<span leaf="">— {alt}</span></p>'
        if alt
        else ""
    )
    return (
        f'<section style="margin:{margin};">'
        '<section style="background:#FFF;border-radius:12px;padding:6px;border:1px solid #E5E7EB;'
        'box-shadow:0 4px 12px -2px rgba(0,0,0,0.08);margin:0 0 8px;">'
        '<section style="margin:0;border-radius:8px;overflow:hidden;">'
        f'<span leaf=""><img src="{src}" alt="{alt}" style="max-width:100%;height:auto;display:block;margin:0 auto;"></span>'
        f'</section></section>{caption}</section>'
    )


def _image(node: Tag) -> str:
    return figure_block(str(node.get("src") or ""), str(node.get("alt") or ""))


def _text_paragraph(content: str) -> str:
    return (
        '<p style="margin:0 0 16px;font-size:14px;line-height:1.9;text-align:justify;color:#374151;">'
        f'{content}</p>'
    )


def _paragraph(node: Tag) -> str:
    images = node.find_all("img")
    if not images:
        return _text_paragraph(_inline_children(node))
    if not node.get_text(strip=True):
        return "".join(_image(image) for image in images)
    # An image followed by a "*图：…*" line on the next source line lands in the same <p>;
    # split it so the image is rendered as a block instead of being dropped by _inline.
    parts: list[str] = []
    run: list[NavigableString | Tag] = []

    def flush() -> None:
        meaningful = [child for child in run if not (isinstance(child, NavigableString) and not child.strip())]
        if meaningful:
            if len(meaningful) == 1 and isinstance(meaningful[0], Tag) and meaningful[0].name == "em":
                parts.append(
                    '<p style="font-size:12px;color:#9CA3AF;text-align:center;margin:0 0 24px;">'
                    f'{_inline_children(meaningful[0])}</p>'
                )
            else:
                parts.append(_text_paragraph("".join(_inline(child) for child in run)))
        run.clear()

    for child in node.children:
        if isinstance(child, Tag) and (child.name == "img" or child.find("img")):
            flush()
            parts.extend(_image(image) for image in ([child] if child.name == "img" else child.find_all("img")))
        elif isinstance(child, Tag) and child.name == "br":
            continue
        else:
            run.append(child)
    flush()
    return "".join(parts)


def _code_block(node: Tag) -> str:
    code = node.find("code")
    text = code.get_text() if code else node.get_text()
    language = "CODE"
    if code:
        for class_name in code.get("class") or []:
            if str(class_name).startswith("language-"):
                language = str(class_name).removeprefix("language-").upper()
                break
    lines = text.rstrip("\n").splitlines() or [""]
    rendered_lines = "".join(
        '<p style="margin:0;font-family:Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#E2E8F0;">'
        f'<span leaf="">{escape(line).replace("  ", "　") or " "}</span></p>'
        for line in lines
    )
    return (
        '<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#1E293B;'
        'box-shadow:0 4px 16px -8px rgba(15,23,42,0.4);">'
        '<section style="display:flex;align-items:center;padding:9px 14px;background:#0F172A;">'
        '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#FF5F56;margin-right:7px;font-size:0;">'
        '<span leaf="">.</span></span>'
        f'<span style="font-size:12px;color:#64748B;font-family:Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">{escape(language)}</span></span>'
        f'</section><section style="padding:11px 14px;">{rendered_lines}</section></section>'
    )


_LIST_STYLES = ("disc", "circle", "square")


def _list(node: Tag, ordered: bool, depth: int = 0) -> str:
    items: list[str] = []
    for item in node.find_all("li", recursive=False):
        text_parts: list[str] = []
        nested: list[str] = []
        for child in item.children:
            if isinstance(child, Tag) and child.name in {"ul", "ol"}:
                nested.append(_list(child, child.name == "ol", depth + 1))
            elif isinstance(child, Tag) and child.name == "p":
                text_parts.append(_inline_children(child))
            elif isinstance(child, NavigableString) and not str(child).strip():
                continue
            else:
                text_parts.append(_inline(child))
        items.append(
            '<li style="margin:0 0 6px;font-size:14px;line-height:1.9;color:#374151;">'
            f'<section style="text-align:justify;">{"".join(text_parts)}</section>{"".join(nested)}</li>'
        )
    tag = "ol" if ordered else "ul"
    list_style = "decimal" if ordered else _LIST_STYLES[min(depth, len(_LIST_STYLES) - 1)]
    margin = "4px 0 4px" if depth else "0 0 18px"
    return (
        f'<{tag} style="list-style-type:{list_style};padding-left:{"1.4em" if depth else "1.6em"};margin:{margin};color:#6B7280;">'
        f'{"".join(items)}</{tag}>'
    )


_LIST_LINE_RE = re.compile(r"^( +)((?:[-*+]|\d+[.)])\s)", re.MULTILINE)


def _normalize_list_indent(markdown_text: str) -> str:
    """Python-Markdown nests lists only at 4-space steps; LLMs usually indent by 2."""
    indents = {len(match.group(1)) for match in _LIST_LINE_RE.finditer(markdown_text)}
    if not any(indent % 4 for indent in indents):
        return markdown_text
    return _LIST_LINE_RE.sub(lambda m: " " * (len(m.group(1)) * 2) + m.group(2), markdown_text)


_HEADING_NUMBER_RE = re.compile(r"^\s*(?:第[一二三四五六七八九十\d]+[章节部分]|[（(]?\d{1,2}(?:\.\d+)*(?:[.)、．）]|\s)|[一二三四五六七八九十]+[、.．])\s*")


def _heading_text(node: Tag) -> str:
    return _HEADING_NUMBER_RE.sub("", node.get_text(strip=True)) or node.get_text(strip=True)


def _table(node: Tag) -> str:
    rows: list[str] = []
    for row_index, row in enumerate(node.find_all("tr")):
        cells: list[str] = []
        for cell in row.find_all(["th", "td"], recursive=False):
            if cell.name == "th":
                style = "background:#059669;color:#fff;font-weight:700;padding:8px 12px;text-align:left;"
            else:
                background = "background:#F9FAFB;" if row_index % 2 == 0 else ""
                style = f"padding:8px 12px;border-bottom:1px solid #E5E7EB;color:#374151;{background}"
            cells.append(f'<{cell.name} style="{style}">{_inline_children(cell)}</{cell.name}>')
        rows.append(f'<tr>{"".join(cells)}</tr>')
    return (
        '<section style="margin-bottom:24px;overflow-x:auto;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:13px;">{"".join(rows)}</table></section>'
    )


def _block(node: Tag, chapter_index: int) -> str:
    name = node.name.lower()
    if name == "h1":
        return ""
    if name == "h2":
        return (
            '<section style="margin:40px 0 20px;display:flex;align-items:baseline;gap:10px;">'
            f'<span style="font-size:22px;font-weight:900;color:#059669;line-height:1;"><span leaf="">{chapter_index:02d}</span></span>'
            f'<span style="font-size:18px;font-weight:800;color:#111827;line-height:1.4;"><span leaf="">{escape(_heading_text(node))}</span></span>'
            '</section>'
        )
    if name == "h3":
        return (
            '<p style="margin:28px 0 14px;font-size:16px;font-weight:800;color:#1C1917;line-height:1.5;'
            f'border-left:4px solid #059669;padding-left:12px;"><span leaf="">{escape(_heading_text(node))}</span></p>'
        )
    if name == "p":
        return _paragraph(node)
    if name == "blockquote":
        return (
            '<section style="margin:0 0 24px;background:#ECFDF5;border-radius:0 10px 10px 0;'
            'border-left:4px solid #059669;padding:16px 20px;">'
            f'<p style="font-size:15px;font-weight:700;color:#065F46;margin:0;line-height:1.8;">{_inline_children(node)}</p></section>'
        )
    if name == "pre":
        return _code_block(node)
    if name == "ul":
        return _list(node, False)
    if name == "ol":
        return _list(node, True)
    if name == "table":
        return _table(node)
    if name == "hr":
        return '<section style="height:1px;background:#E5E7EB;margin:28px 0;"><span leaf=""><br></span></section>'
    return ""


_CODE_SEGMENT_RE = re.compile(r"(```[\s\S]*?```|`[^`\n]+`)")
_DISPLAY_MATH_RE = re.compile(r"\$\$([\s\S]+?)\$\$")
_INLINE_MATH_RE = re.compile(r"(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)")
_BLOCK_PLACEHOLDER_RE = re.compile(r'<p style="[^"]*"><span leaf="">PWMATHB(\d+)Z</span></p>')
_INLINE_PLACEHOLDER_RE = re.compile(r"PWMATH([BI])(\d+)Z")


def _extract_math(markdown_text: str) -> tuple[str, list[tuple[str, bool]]]:
    """Replace $$..$$ / $..$ outside code with letter-only placeholders markdown leaves alone."""
    formulas: list[tuple[str, bool]] = []

    def display(match: re.Match[str]) -> str:
        formulas.append((match.group(1).strip(), True))
        return f"\n\nPWMATHB{len(formulas) - 1}Z\n\n"

    def inline(match: re.Match[str]) -> str:
        formulas.append((match.group(1).strip(), False))
        return f"PWMATHI{len(formulas) - 1}Z"

    pieces = _CODE_SEGMENT_RE.split(markdown_text)
    for index in range(0, len(pieces), 2):
        piece = _DISPLAY_MATH_RE.sub(display, pieces[index])
        pieces[index] = _INLINE_MATH_RE.sub(inline, piece)
    return "".join(pieces), formulas


def _formula_html(expr: str, display: bool, asset_dir: Path | None) -> str:
    if not display:
        text_html = latex_to_inline_html(expr)
        if text_html is not None:
            return text_html
    if asset_dir is not None:
        try:
            rendered = render_formula_png(expr, asset_dir / "formulas", display=display)
        except Exception:  # mathtext raises a variety of parse errors
            rendered = None
        if rendered is not None:
            src = escape(rendered.path.relative_to(asset_dir).as_posix(), quote=True)
            alt = escape(expr, quote=True)
            if display:
                return (
                    '<section style="margin:4px 0 20px;text-align:center;overflow-x:auto;">'
                    f'<span leaf=""><img src="{src}" alt="{alt}" style="width:{rendered.width}px;'
                    'max-width:100%;height:auto;display:inline-block;"></span></section>'
                )
            return (
                f'<img src="{src}" alt="{alt}" style="display:inline-block;vertical-align:middle;'
                f'height:{rendered.height}px;width:auto;margin:0 2px;">'
            )
    return formula_fallback_html(expr, display=display)


def _restore_math(html: str, formulas: list[tuple[str, bool]], asset_dir: Path | None) -> str:
    if not formulas:
        return html
    rendered = [_formula_html(expr, display, asset_dir) for expr, display in formulas]
    html = _BLOCK_PLACEHOLDER_RE.sub(lambda m: rendered[int(m.group(1))], html)
    # Remaining placeholders sit inside <span leaf="">text</span>; close the leaf around them.
    html = _INLINE_PLACEHOLDER_RE.sub(lambda m: f'</span>{rendered[int(m.group(2))]}<span leaf="">', html)
    return html.replace('<span leaf=""></span>', "")


def render_markdown_for_wechat(
    markdown_text: str,
    *,
    fallback_title: str = "微信公众号文章",
    asset_dir: Path | None = None,
    header_html: str = "",
) -> RenderedMarkdown:
    """Render Markdown into the 摸鱼绿 WeChat fragment.

    ``asset_dir`` is the directory the HTML will live in; when given, formulas are
    rendered to ``asset_dir/formulas/*.png`` and referenced relatively.
    """
    protected, formulas = _extract_math(_normalize_list_indent(markdown_text))
    source_html = markdown.markdown(
        protected,
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )
    soup = BeautifulSoup(source_html, "html.parser")
    first_h1 = soup.find("h1")
    title = first_h1.get_text(" ", strip=True) if first_h1 else fallback_title

    body: list[str] = []
    chapter_index = 0
    for child in soup.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h2":
            chapter_index += 1
        body.append(_block(child, chapter_index))

    content = _restore_math("".join(body), formulas, asset_dir)
    title = _INLINE_PLACEHOLDER_RE.sub(lambda m: formulas[int(m.group(2))][0], title)
    html = (
        '<section style="max-width:677px;margin:0 auto;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'
        "'PingFang SC','Microsoft YaHei',sans-serif;color:#374151;line-height:1.75;letter-spacing:0.5px;overflow-x:hidden;\">"
        f'{header_html}<section style="padding:0 20px;">{content}</section></section>'
    )
    return RenderedMarkdown(title=title[:64], html=html)


def paper_info_card(
    *,
    title: str,
    authors: list[str],
    affiliations: list[str] | None = None,
    venue: str = "",
    year: int | None = None,
    arxiv_id: str = "",
) -> str:
    """Source card shown above the article body: title, authors, affiliations, venue."""
    author_text = ", ".join(authors[:12]) + (" 等" if len(authors) > 12 else "")
    source = " | ".join(part for part in [venue, str(year) if year else "", f"arXiv:{arxiv_id}" if arxiv_id else ""] if part)

    def label(text: str) -> str:
        return (
            '<p style="font-size:12px;color:#059669;font-weight:700;margin:0 0 2px;line-height:1.6;">'
            f'<span leaf="">{text}</span></p>'
        )

    def value(text: str, *, strong: bool = False, last: bool = True) -> str:
        style = "font-size:14px;font-weight:700;color:#111827;" if strong else "font-size:12px;color:#4B5563;"
        margin = "0 0 10px" if last else "0 0 2px"
        return f'<p style="{style}margin:{margin};line-height:1.7;"><span leaf="">{escape(text)}</span></p>'

    rows = [label("标题"), value(title, strong=True)]
    if author_text:
        rows += [label("作者"), value(author_text)]
    if affiliations:
        shown = affiliations[:8]
        rows.append(label("单位"))
        rows += [value(f"{index}. {name}", last=index == len(shown)) for index, name in enumerate(shown, 1)]
    if source:
        rows += [label("来源"), value(source)]
    return (
        '<section style="margin:0 20px 28px;padding:16px 18px;background:#F0FDF4;border-radius:10px;'
        f'border-left:4px solid #059669;">{"".join(rows)}</section>'
    )
