"""Assemble the paper text handed to the summary prompt.

Unlike ``PaperAssetsBundle.llm_context`` (one top-level section per target, no
subsections), the summary needs the whole main body: every subsection of the
method and experiment sections, compact result tables, and the list of figures
it may embed. Appendix sections (everything after the conclusion except
limitations) are left out, and over-budget text is trimmed proportionally with
experiments trimmed least.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from paper_wiki.assets.models import PaperAssetsBundle, SectionAsset

DEFAULT_SUMMARY_CONTEXT_CHARS = 60000
MIN_SECTION_CHARS = 600
CAPTION_CHARS = 400

_CONCLUSION_RE = re.compile(r"conclu|summary and (future|outlook)", re.IGNORECASE)
_KEEP_AFTER_CONCLUSION_RE = re.compile(r"^limitations?\b|broader impact", re.IGNORECASE)
_STOP_RE = re.compile(r"^(appendix|appendices|supplementary|references|bibliography|acknowledg)", re.IGNORECASE)
_SECTION_WEIGHTS = (
    (re.compile(r"experiment|evaluation|result|ablation|analys|benchmark|empirical", re.IGNORECASE), 1.3),
    (re.compile(r"introduction|motivation", re.IGNORECASE), 0.8),
    (re.compile(r"conclu|limitation|discussion", re.IGNORECASE), 0.7),
    (re.compile(r"related|background|prior work|preliminar", re.IGNORECASE), 0.5),
)
_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_NUMERIC_CELL_RE = re.compile(r"^[*\s]*[-+]?\d[\d.,]*\s*%?(?:\s*[±/]\s*[-+]?\d[\d.,]*\s*%?)?[*\s]*$")


@dataclass
class _Block:
    section: SectionAsset
    heading: str
    text: str
    weight: float


def build_summary_context(bundle: PaperAssetsBundle, max_chars: int | None = DEFAULT_SUMMARY_CONTEXT_CHARS) -> str:
    sections = main_body_sections(bundle)
    if not sections:
        return bundle.llm_context(max_chars=max_chars)

    figure_paths = _figure_path_index(bundle)
    blocks = [
        _Block(
            section=section,
            heading="#" * min(max(section.level, 1) + 1, 4) + " " + section.title.strip(),
            text=compact_tables(mark_inline_figures(section.text, figure_paths)).strip(),
            weight=_weight(group_title),
        )
        for section, group_title in sections
    ]
    figures = _figure_list(bundle, {section.id for section, _ in sections})
    header = f"# {bundle.title}\n\n## Abstract\n\n{bundle.abstract.strip()}\n"

    if max_chars and max_chars > 0:
        budget = max_chars - len(header) - len(figures) - sum(len(block.heading) + 4 for block in blocks)
        _fit_blocks(blocks, max(budget, MIN_SECTION_CHARS * len(blocks)))

    body = "\n\n".join(f"{block.heading}\n\n{block.text}" if block.text else block.heading for block in blocks)
    return f"{header}\n{body}\n\n{figures}".strip() + "\n"


def main_body_sections(bundle: PaperAssetsBundle) -> list[tuple[SectionAsset, str]]:
    """Main-body sections in order, each paired with its top-level section title."""
    result: list[tuple[SectionAsset, str]] = []
    group_title = ""
    including = True
    after_conclusion = False
    for section in sorted(bundle.sections.sections, key=lambda item: item.order):
        if section.type == "abstract":
            continue
        if not section.parent_id:
            title = section.title.strip()
            if _STOP_RE.match(title):
                break
            group_title = title
            including = not after_conclusion or bool(_KEEP_AFTER_CONCLUSION_RE.search(title))
            if _CONCLUSION_RE.search(title):
                after_conclusion = True
        if including:
            result.append((section, group_title))
    return result


def _weight(group_title: str) -> float:
    for pattern, weight in _SECTION_WEIGHTS:
        if pattern.search(group_title):
            return weight
    return 1.0


def _fit_blocks(blocks: list[_Block], budget: int) -> None:
    """Trim every block by a shared ratio scaled by its weight until the total fits."""
    lengths = [len(block.text) for block in blocks]
    if sum(lengths) <= budget:
        return

    def allotted(scale: float) -> list[int]:
        return [
            min(length, max(MIN_SECTION_CHARS, int(scale * block.weight * length)))
            for block, length in zip(blocks, lengths)
        ]

    low, high = 0.0, 1.0 / min(block.weight for block in blocks)
    for _ in range(30):
        middle = (low + high) / 2
        if sum(allotted(middle)) > budget:
            high = middle
        else:
            low = middle
    for block, limit in zip(blocks, allotted(low)):
        block.text = _truncate(block.text, limit)


def _truncate(text: str, limit: int) -> str:
    """Keep leading prose paragraphs within ``limit``; compact result tables are always kept."""
    if len(text) <= limit:
        return text
    paragraphs = re.split(r"\n{2,}", text)
    is_table = [paragraph.startswith(("[TABLE", "**Table")) for paragraph in paragraphs]
    table_chars = sum(len(paragraph) for paragraph, table in zip(paragraphs, is_table) if table)
    prose_limit = max(limit - table_chars, int(limit * 0.3))
    kept: list[str] = []
    used = 0
    dropped = False
    for paragraph, table in zip(paragraphs, is_table):
        if table:
            kept.append(paragraph)
        elif used + len(paragraph) <= prose_limit:
            kept.append(paragraph)
            used += len(paragraph) + 2
        elif used == 0:
            kept.append(paragraph[:prose_limit].rsplit(" ", 1)[0])
            used = prose_limit
            dropped = True
        else:
            dropped = True
    if dropped:
        kept.append("[……本节其余内容已省略]")
    return "\n\n".join(kept)


def main_body_figures(bundle: PaperAssetsBundle) -> list[tuple[str, str, str]]:
    """Main-body figures as ``(asset_path, section_title, short_caption)``; appendix figures are skipped."""
    section_ids = {section.id for section, _ in main_body_sections(bundle)}
    titles = {section.id: section.title for section in bundle.sections.sections}
    result = []
    for figure in bundle.figures.figures:
        if not figure.asset_path or (figure.section_id and figure.section_id not in section_ids):
            continue
        caption = re.sub(r"\s+", " ", figure.caption).strip()
        if len(caption) > CAPTION_CHARS:
            caption = caption[:CAPTION_CHARS].rsplit(" ", 1)[0] + " …"
        result.append((figure.asset_path, titles.get(figure.section_id, ""), caption))
    return result


def _figure_list(bundle: PaperAssetsBundle, section_ids: set[str]) -> str:
    lines = [
        f"- [FIGURE] path: {path} | 所在章节: {where or '未知'} | 原图注: {caption or '无'}"
        for path, where, caption in main_body_figures(bundle)
    ]
    if not lines:
        return "## 可用配图\n\n（本文没有可用的配图，正文中不要插入任何图片。）"
    return "## 可用配图（插图只能使用这里列出的 path）\n\n" + "\n".join(lines)


_INLINE_IMAGE_RE = re.compile(r"^\s*!\[[^\]]*\]\(([^)\s]+)\)\s*$", re.MULTILINE)
_INLINE_CAPTION_RE = re.compile(r"^\s*\*{1,2}Figure:.*$", re.MULTILINE)


def _figure_path_index(bundle: PaperAssetsBundle) -> dict[str, str]:
    index: dict[str, str] = {}
    for figure in bundle.figures.figures:
        if not figure.asset_path:
            continue
        for path in (figure.asset_path, figure.source_path):
            if path:
                index.setdefault(path.rsplit("/", 1)[-1].rsplit(".", 1)[0], figure.asset_path)
    return index


def mark_inline_figures(text: str, figure_paths: dict[str, str]) -> str:
    """Replace the paper's own image/caption lines with a ``[FIGURE: path]`` marker at the same spot.

    Captions are listed once in the trailing figure list; keeping only the marker
    avoids handing the model an English-caption example to imitate.
    """

    def repl(match: re.Match[str]) -> str:
        stem = match.group(1).rsplit("/", 1)[-1].rsplit(".", 1)[0]
        target = figure_paths.get(stem)
        return f"\n[FIGURE: {target}]\n" if target else "\n"

    text = _INLINE_CAPTION_RE.sub("", _INLINE_IMAGE_RE.sub(repl, text))
    text = re.sub(r"(\[FIGURE: [^\]]+\])(?:\s*\1)+", r"\1", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def compact_tables(text: str) -> str:
    """Turn ```latex tabular blocks into short pipe-separated tables the model can read."""

    def repl(match: re.Match[str]) -> str:
        source = match.group(2)
        if "\\begin{tabular" not in source:
            return match.group(0)
        rows = _tabular_rows(source)
        if not rows:
            return ""
        caption = _latex_caption(source)
        head = f"[TABLE] {caption}\n" if caption else "[TABLE]\n"
        return head + "\n".join(rows)

    text = _CODE_BLOCK_RE.sub(repl, text)
    # "**Table:**" headers whose caption only lived inside the LaTeX block are now redundant.
    return re.sub(r"\*\*Table:\s*\*\*\n+(?=\[TABLE\])", "", text)


def _latex_caption(source: str) -> str:
    start = source.find("\\caption")
    if start < 0:
        return ""
    brace = source.find("{", start)
    end = _matching_brace(source, brace) if brace >= 0 else None
    if end is None:
        return ""
    return _clean_cell(source[brace + 1 : end])[:CAPTION_CHARS]


def _matching_brace(text: str, start: int) -> int | None:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{" and text[index - 1 : index] != "\\":
            depth += 1
        elif text[index] == "}" and text[index - 1 : index] != "\\":
            depth -= 1
            if depth == 0:
                return index
    return None


def _tabular_rows(source: str) -> list[str]:
    begin = re.search(r"\\begin\{tabular\*?\}", source)
    end = re.search(r"\\end\{tabular\*?\}", source)
    if not begin or not end or end.start() < begin.end():
        return []
    position = begin.end()
    # Skip the width argument of tabular* and the column spec.
    for _ in range(2 if "tabular*" in begin.group(0) else 1):
        while position < len(source) and source[position].isspace():
            position += 1
        if position < len(source) and source[position] == "{":
            closing = _matching_brace(source, position)
            position = (closing + 1) if closing is not None else position
    body = source[position : end.start()]
    body = re.sub(r"(?<!\\)%.*", "", body)
    body = re.sub(
        r"\\(?:toprule|midrule|bottomrule|hline|addlinespace|specialrule|cmidrule|cline)\*?(?:\([^)]*\))?(?:\[[^\]]*\])?(?:\{[^{}]*\})*",
        "",
        body,
    )
    grid: list[list[str]] = []
    for raw_row in re.split(r"\\\\(?:\[[^\]]*\])?", body):
        cells: list[str] = []
        for raw_cell in re.split(r"(?<!\\)&", raw_row):
            span = re.search(r"\\multicolumn\{(\d+)\}", raw_cell)
            cells.extend([_clean_cell(raw_cell)] * (int(span.group(1)) if span else 1))
        if any(cells):
            grid.append(cells)
    return _label_rows(grid)


def _label_rows(grid: list[list[str]]) -> list[str]:
    """Write each data cell as ``列名=值`` so multi-level headers (e.g. 2Wiki F1 / 2Wiki G-E) stay unambiguous."""

    def numeric_cells(row: list[str]) -> int:
        return sum(1 for cell in row[1:] if _NUMERIC_CELL_RE.match(cell))

    def group_label(row: list[str]) -> str | None:
        values = {cell for cell in row if cell}
        return values.pop() if len(values) == 1 and not numeric_cells(row) else None

    first_data = next((index for index, row in enumerate(grid) if numeric_cells(row)), None)
    if not first_data:
        return [" | ".join(row) for row in grid]
    headers = [row for row in grid[:first_data] if group_label(row) is None]
    leading_groups = [f"【{label}】" for row in grid[:first_data] if (label := group_label(row))]
    width = max(len(row) for row in grid)
    labels = []
    for column in range(width):
        parts: list[str] = []
        for header in headers:
            if column < len(header) and header[column] and header[column] not in parts:
                parts.append(header[column])
        labels.append(" ".join(parts) or f"列{column + 1}")

    lines: list[str] = leading_groups
    previous_name = ""
    for row in grid[first_data:]:
        if (label := group_label(row)) is not None:
            lines.append(f"【{label}】")
            continue
        name = row[0] or previous_name or "-"
        previous_name = name
        pairs = [f"{labels[column]}={row[column]}" for column in range(1, len(row)) if row[column]]
        lines.append(f"{name}: " + "; ".join(pairs))
    return lines


def _clean_cell(cell: str) -> str:
    cell = re.sub(r"\\(?:multicolumn|multirow)\{[^{}]*\}(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}", "", cell)
    cell = re.sub(r"\\(?:textbf|mathbf|bm)\{((?:[^{}]|\{[^{}]*\})*)\}", r"**\1**", cell)
    cell = re.sub(r"\\(?:rowcolor|cellcolor|color)(?:\[[^\]]*\])?\{[^{}]*\}", "", cell)
    cell = cell.replace("\\checkmark", "✓").replace("\\xmark", "✗").replace("\\cmark", "✓")
    cell = cell.replace("\\%", "%").replace("\\&", "&").replace("~", " ")
    # Arguments that are bare macros (icon markers) would otherwise glue onto the following word.
    cell = re.sub(r"\{\s*\\[a-zA-Z]+\*?\s*\}", " ", cell)
    for _ in range(3):
        cell = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", cell)
    cell = re.sub(r"\\[a-zA-Z]+\*?", " ", cell)
    cell = re.sub(r"[{}$]", "", cell)
    return re.sub(r"\s+", " ", cell).strip()
