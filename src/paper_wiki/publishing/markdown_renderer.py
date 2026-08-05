from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag
import markdown


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


def _image(node: Tag) -> str:
    src = _safe_image_src(str(node.get("src") or ""))
    # Relative local image paths intentionally have no URL scheme and are kept.
    if not src:
        return ""
    alt = escape(str(node.get("alt") or ""))
    caption = (
        f'<p style="font-size:12px;color:#9CA3AF;text-align:center;margin:0 0 24px;">'
        f'<span leaf="">— {alt}</span></p>'
        if alt
        else ""
    )
    return (
        '<section style="background:#FFF;border-radius:12px;padding:6px;border:1px solid #E5E7EB;'
        'box-shadow:0 4px 12px -2px rgba(0,0,0,0.08);margin:0 0 8px;">'
        '<section style="margin:0;border-radius:8px;overflow:hidden;">'
        f'<span leaf=""><img src="{src}" alt="{alt}" style="max-width:100%;height:auto;display:block;margin:0 auto;"></span>'
        f'</section></section>{caption}'
    )


def _paragraph(node: Tag) -> str:
    images = node.find_all("img")
    if images and not node.get_text(strip=True):
        return "".join(_image(image) for image in images)
    return (
        '<p style="margin:0 0 16px;font-size:14px;line-height:1.9;text-align:justify;color:#374151;">'
        f'{_inline_children(node)}</p>'
    )


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


def _list(node: Tag, ordered: bool) -> str:
    items: list[str] = []
    for index, item in enumerate(node.find_all("li", recursive=False), start=1):
        marker = str(index) if ordered else "•"
        items.append(
            '<section style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">'
            '<span style="display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;'
            'background:#059669;color:#fff;font-size:11px;font-weight:700;border-radius:50%;margin-top:2px;">'
            f'<span leaf="">{marker}</span></span>'
            '<p style="font-size:14px;color:#374151;margin:0;line-height:1.9;flex:1;">'
            f'{_inline_children(item)}</p></section>'
        )
    return f'<section style="margin-bottom:24px;">{"".join(items)}</section>'


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
            '<section style="margin-top:48px;margin-bottom:24px;">'
            '<section style="display:flex;align-items:center;gap:16px;margin-bottom:24px;">'
            '<section style="text-align:center;flex-shrink:0;">'
            f'<p style="margin:0;font-size:28px;font-weight:900;color:#059669;line-height:1;"><span leaf="">{chapter_index:02d}</span></p>'
            '<p style="margin:0;font-size:8px;font-weight:700;color:#D1D5DB;letter-spacing:2px;"><span leaf="">PART</span></p>'
            '</section><span style="width:1px;height:36px;background:#E5E7EB;flex-shrink:0;"><span leaf=""><br></span></span>'
            f'<p style="margin:0;font-size:17px;font-weight:900;color:#111827;"><span leaf="">{escape(node.get_text(strip=True))}</span></p>'
            '</section></section>'
        )
    if name == "h3":
        return (
            '<p style="margin:28px 0 14px;font-size:16px;font-weight:800;color:#1C1917;line-height:1.5;'
            f'border-left:4px solid #059669;padding-left:12px;"><span leaf="">{escape(node.get_text(strip=True))}</span></p>'
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


def render_markdown_for_wechat(markdown_text: str, *, fallback_title: str = "微信公众号文章") -> RenderedMarkdown:
    source_html = markdown.markdown(
        markdown_text,
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )
    soup = BeautifulSoup(source_html, "html.parser")
    first_h1 = soup.find("h1")
    title = first_h1.get_text(" ", strip=True) if first_h1 else fallback_title
    headings = [heading.get_text(" ", strip=True) for heading in soup.find_all("h2")]

    toc = ""
    if len(headings) >= 2:
        cards = "".join(
            '<section style="flex:1;background:#ECFDF5;border:1px solid #A7F3D0;border-radius:10px;padding:10px;">'
            f'<p style="font-size:10px;color:#059669;margin:0 0 4px;font-weight:700;"><span leaf="">PART {index:02d}</span></p>'
            f'<p style="font-size:13px;color:#111827;margin:0;font-weight:700;"><span leaf="">{escape(heading)}</span></p></section>'
            for index, heading in enumerate(headings[:3], start=1)
        )
        toc = f'<section style="display:flex;gap:8px;margin:0 20px 28px;">{cards}</section>'

    body: list[str] = []
    chapter_index = 0
    for child in soup.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h2":
            chapter_index += 1
        body.append(_block(child, chapter_index))

    cover = (
        '<section style="margin:0 0 28px;background:#fff;border:1.5px solid rgba(5,150,105,0.15);'
        'border-radius:20px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">'
        '<section style="padding:28px;">'
        '<p style="font-size:11px;font-weight:700;letter-spacing:3px;color:#059669;margin:0 0 20px;"><span leaf="">PAPER · WIKI</span></p>'
        f'<p style="font-size:26px;font-weight:900;color:#111827;margin:0;line-height:1.25;"><span leaf="">{escape(title)}</span></p>'
        '</section><section style="height:8px;background:linear-gradient(135deg,#059669,#10B981);"><span leaf=""><br></span></section></section>'
    )
    footer = (
        '<section style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:16px;padding:26px 20px;'
        'text-align:center;margin:32px 0 24px;">'
        '<p style="font-size:13px;font-weight:700;color:#111827;margin:0 0 8px;line-height:1.7;">'
        '<span leaf="">如果你觉得这篇文章有收获，欢迎点赞、在看、转发。</span></p>'
        '<p style="font-size:10px;color:#9CA3AF;letter-spacing:1px;margin:0;"><span leaf="">THANKS FOR READING</span></p></section>'
    )
    html = (
        '<section style="max-width:677px;margin:0 auto;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'
        "'PingFang SC','Microsoft YaHei',sans-serif;color:#374151;line-height:1.75;letter-spacing:0.5px;overflow-x:hidden;\">"
        f'{cover}{toc}<section style="padding:0 20px;">{"".join(body)}{footer}</section></section>'
    )
    return RenderedMarkdown(title=title[:64], html=html)
