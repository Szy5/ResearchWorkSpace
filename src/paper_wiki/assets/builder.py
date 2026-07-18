from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from paper_wiki.assets.models import (
    AssetCounts,
    AssetsBuildResult,
    AssetsManifest,
    CitationContext,
    FigureAsset,
    FiguresDoc,
    PaperAssetMeta,
    ReferenceEntry,
    ReferencesDoc,
    SectionAsset,
    SectionsDoc,
    SourceFileHash,
    SourceProvenance,
)
from paper_wiki.core.config import Settings, get_settings
from paper_wiki.core.validation import validate_slug
from paper_wiki.ingestion.latex_parser import LaTeXParser
from paper_wiki.ingestion.summary_figure_converter import convert_pdf_first_page_to_jpg, find_file_case_insensitive

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
UNSUPPORTED_IMAGE_SUFFIXES = {".eps"}
PANDOC_MARKDOWN_FORMAT = "markdown+tex_math_dollars+pipe_tables-simple_tables-multiline_tables-grid_tables"


class PaperAssetsBuilder:
    """Build deterministic, reusable paper assets from raw LaTeX."""

    def __init__(self, settings: Settings | None = None, parser: LaTeXParser | None = None) -> None:
        self.settings = settings or get_settings()
        self.parser = parser or LaTeXParser(max_chars=self.settings.max_parse_chars)
        self.warnings: list[str] = []

    def build(self, slug: str, overwrite: bool = False) -> AssetsBuildResult:
        """Build assets/{paper.md, sections.json, figures/, references.json} for one slug."""
        self._validate_slug(slug)
        self.warnings = []

        paper_dir = self.settings.resolved_raw_dir() / slug
        artifact_dir = self.settings.resolved_artifacts_dir() / slug
        assets_dir = artifact_dir / "assets"
        figures_dir = assets_dir / "figures"

        manifest_path = artifact_dir / "manifest.json"
        paper_path = assets_dir / "paper.md"
        sections_path = assets_dir / "sections.json"
        figures_manifest_path = figures_dir / "manifest.json"
        references_path = assets_dir / "references.json"
        output_paths = [manifest_path, paper_path, sections_path, figures_manifest_path, references_path]
        existing = [path for path in output_paths if path.exists()]
        if existing and not overwrite:
            raise FileExistsError(f"assets already exist for {slug}. Use overwrite=True or --overwrite.")

        paper_dir = paper_dir.resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)
        figures_dir.mkdir(parents=True, exist_ok=True)

        entry, merged = self._load_merged_latex(paper_dir)
        cleaned = self.parser._strip_comments(merged)
        title = self.parser._extract_command(cleaned, "title") or slug
        authors = self.parser._extract_authors(cleaned)
        abstract = self.parser._extract_abstract(cleaned)

        sections = self._extract_sections(cleaned, abstract)
        figures = self._extract_figures(cleaned, sections, paper_dir, figures_dir)
        figure_links = self._figure_links(figures)
        sections = self._extract_sections(cleaned, abstract, figure_links=figure_links)
        figure_ids_by_label: dict[str, list[str]] = {}
        for figure in figures:
            if figure.label:
                figure_ids_by_label.setdefault(figure.label, []).append(figure.id)
        for section in sections:
            section.figure_ids = [
                figure_id
                for label in section.labels
                for figure_id in figure_ids_by_label.get(label, [])
            ]

        references = self._extract_references(paper_dir, sections)
        paper_markdown = self._build_paper_markdown(title, authors, abstract, sections)

        sections_doc = SectionsDoc(sections=sections)
        figures_doc = FiguresDoc(figures=figures)
        references_doc = ReferencesDoc(references=references)
        now = datetime.now(timezone.utc).isoformat()
        manifest = AssetsManifest(
            slug=slug,
            created_at=now,
            updated_at=now,
            paper=PaperAssetMeta(title=title, authors=authors, abstract=abstract),
            source=SourceProvenance(
                raw_dir=str((self.settings.resolved_raw_dir() / slug).relative_to(self.settings.project_root))
                if (self.settings.resolved_raw_dir() / slug).is_relative_to(self.settings.project_root)
                else str(self.settings.resolved_raw_dir() / slug),
                entry_file=str(entry.relative_to(paper_dir)),
                source_files=self._source_file_hashes(paper_dir),
            ),
            counts=AssetCounts(
                sections=len(sections_doc.sections),
                figures=len(figures_doc.figures),
                references=len(references_doc.references),
            ),
            warnings=self.warnings,
        )

        self._write_text(paper_path, paper_markdown)
        self._write_json(sections_path, sections_doc.model_dump(mode="json"))
        self._write_json(figures_manifest_path, figures_doc.model_dump(mode="json"))
        self._write_json(references_path, references_doc.model_dump(mode="json"))
        self._write_json(manifest_path, manifest.model_dump(mode="json"))

        return AssetsBuildResult(
            slug=slug,
            artifact_dir=artifact_dir,
            manifest_path=manifest_path,
            paper_path=paper_path,
            sections_path=sections_path,
            figures_dir=figures_dir,
            figures_manifest_path=figures_manifest_path,
            references_path=references_path,
        )

    def _load_merged_latex(self, paper_dir: Path) -> tuple[Path, str]:
        if not paper_dir.exists() or not paper_dir.is_dir():
            raise FileNotFoundError(f"Paper directory does not exist: {paper_dir}")
        self.parser._source_files = []
        entry = self.parser._find_entry_file(paper_dir)
        merged = self.parser._inline_inputs(entry, paper_dir)
        return entry, merged

    def _extract_sections(
        self,
        text: str,
        abstract: str,
        *,
        figure_links: dict[str, str] | None = None,
    ) -> list[SectionAsset]:
        sections: list[SectionAsset] = []
        order = 0
        if abstract:
            sections.append(
                SectionAsset(
                    id="sec-abstract",
                    type="abstract",
                    title="Abstract",
                    level=0,
                    order=order,
                    text=abstract,
                    labels=self._labels(abstract),
                    citations=self._citations(abstract),
                )
            )
            order += 1

        heading = re.compile(
            r"\\(?P<level>section|subsection)\*?(?:\[[^\]]*\])?\{(?P<title>[^{}]+)\}",
            flags=re.IGNORECASE,
        )
        matches = list(heading.finditer(text))
        parent_id = ""
        seen: dict[str, int] = {}
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            title = self.parser._clean_inline_latex(match.group("title")).strip() or "Untitled"
            level_name = match.group("level").lower()
            level = 1 if level_name == "section" else 2
            base_id = self._slugify_id(f"sec-{title}")
            seen[base_id] = seen.get(base_id, 0) + 1
            section_id = base_id if seen[base_id] == 1 else f"{base_id}-{seen[base_id]}"
            if level == 1:
                parent_id = section_id
            raw_content = text[start:end]
            normalized = self._normalize_section_markdown(raw_content, figure_links or {})
            sections.append(
                SectionAsset(
                    id=section_id,
                    type=level_name,
                    title=title,
                    level=level,
                    order=order,
                    parent_id="" if level == 1 else parent_id,
                    text=normalized,
                    labels=self._labels(raw_content),
                    citations=self._citations(raw_content),
                )
            )
            order += 1
        return sections

    def _extract_figures(
        self,
        text: str,
        sections: list[SectionAsset],
        paper_dir: Path,
        figures_dir: Path,
    ) -> list[FigureAsset]:
        section_for_label: dict[str, str] = {}
        for section in sections:
            for label in section.labels:
                section_for_label.setdefault(label, section.id)

        figure_env = re.compile(
            r"\\begin\{(?P<env>figure\*?|wrapfigure)\}(?P<body>.*?)\\end\{(?P=env)\}",
            flags=re.DOTALL | re.IGNORECASE,
        )
        figures: list[FigureAsset] = []
        used_ids: set[str] = set()
        used_names: set[str] = set()
        for env_index, match in enumerate(figure_env.finditer(text), start=1):
            body = match.group("body")
            caption = self._first_caption(body)
            label = self._first_label(body)
            section_id = section_for_label.get(label, self._section_for_offset(text, match.start(), sections))
            graphics = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", body)
            for graphic_index, graphic in enumerate(graphics, start=1):
                source = self._resolve_graphic_path(graphic.strip(), paper_dir)
                figure_id = self._unique_id(self._figure_id(label, graphic, env_index, graphic_index), used_ids)
                asset_path = ""
                status = "missing"
                source_rel = graphic.strip()
                source_hash = ""
                media_type = ""
                if source is not None:
                    source_rel = str(source.relative_to(paper_dir))
                    source_hash = self._sha256(source)
                    media_type = source.suffix.lower().lstrip(".")
                    output_name = self._unique_figure_name(figure_id, source, used_names)
                    output_path = figures_dir / output_name
                    try:
                        status = self._materialize_figure(source, output_path)
                        if status in {"copied", "rendered"}:
                            asset_path = f"assets/figures/{output_name}"
                    except Exception as exc:
                        status = "unsupported"
                        self.warnings.append(f"figure conversion failed: {source_rel}: {exc}")
                else:
                    self.warnings.append(f"figure source not found: {graphic}")

                figures.append(
                    FigureAsset(
                        id=figure_id,
                        label=label,
                        caption=caption,
                        source_path=source_rel,
                        asset_path=asset_path,
                        section_id=section_id,
                        status=status,
                        source_sha256=source_hash,
                        media_type=media_type,
                    )
                )
        return figures

    def _extract_references(self, paper_dir: Path, sections: list[SectionAsset]) -> list[ReferenceEntry]:
        citation_contexts: dict[str, list[CitationContext]] = {}
        for section in sections:
            if not section.citations:
                continue
            context = self._compact_context(section.text)
            for key in section.citations:
                citation_contexts.setdefault(key, []).append(CitationContext(section_id=section.id, text=context))

        entries = self._parse_bib_files(paper_dir)
        if not entries:
            entries = self._parse_bbl_files(paper_dir)

        for key, contexts in citation_contexts.items():
            entries.setdefault(key, ReferenceEntry(key=key))
            entries[key].citation_contexts = contexts
        for key, entry in entries.items():
            if key in citation_contexts:
                entry.citation_contexts = citation_contexts[key]
        return [entries[key] for key in sorted(entries)]

    def _parse_bib_files(self, paper_dir: Path) -> dict[str, ReferenceEntry]:
        entries: dict[str, ReferenceEntry] = {}
        for bib_path in sorted(paper_dir.rglob("*.bib")):
            text = bib_path.read_text(encoding="utf-8", errors="ignore")
            for raw_entry in self._bib_entries(text):
                key_match = re.match(r"@\w+\s*\{\s*([^,\s]+)\s*,", raw_entry, flags=re.DOTALL)
                if not key_match:
                    continue
                key = key_match.group(1).strip()
                fields = self._bib_fields(raw_entry)
                entries[key] = ReferenceEntry(
                    key=key,
                    title=self.parser._clean_inline_latex(fields.get("title", "")),
                    authors=self._split_authors(fields.get("author", "")),
                    year=self._parse_year(fields.get("year", "")),
                    venue=fields.get("booktitle", "") or fields.get("journal", "") or fields.get("venue", ""),
                    doi=fields.get("doi", ""),
                    arxiv_id=self._arxiv_id(fields.get("eprint", "") or fields.get("archiveprefix", "")),
                    url=fields.get("url", ""),
                    raw_bibtex=raw_entry.strip(),
                )
        return entries

    def _parse_bbl_files(self, paper_dir: Path) -> dict[str, ReferenceEntry]:
        entries: dict[str, ReferenceEntry] = {}
        pattern = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^{}]+)\}(.*?)(?=\\bibitem|\Z)", re.DOTALL)
        for bbl_path in sorted(paper_dir.rglob("*.bbl")):
            text = bbl_path.read_text(encoding="utf-8", errors="ignore")
            for match in pattern.finditer(text):
                key = match.group(1).strip()
                body = self.parser._clean_inline_latex(match.group(2))
                entries[key] = ReferenceEntry(key=key, title=body[:180], raw_bibtex=match.group(0).strip())
        return entries

    def _build_paper_markdown(
        self,
        title: str,
        authors: list[str],
        abstract: str,
        sections: list[SectionAsset],
    ) -> str:
        parts = [f"# {title}".strip()]
        if authors:
            parts.append("Authors: " + "; ".join(authors))
        if abstract:
            parts.append("## Abstract\n\n" + abstract.strip())
        for section in sections:
            if section.type == "abstract":
                continue
            heading = "#" * min(max(section.level + 1, 2), 6)
            if section.text.strip():
                parts.append(f"{heading} {section.title}\n\n{section.text.strip()}")
        return "\n\n".join(part for part in parts if part.strip()) + "\n"

    def _normalize_section_markdown(self, text: str, figure_links: dict[str, str]) -> str:
        """Normalize LaTeX section content for canonical assets without destroying math/tables."""
        text = self.parser._strip_comments(text)
        text = self._replace_figures_with_markdown(text, figure_links)
        text = self._replace_tables_with_fenced_latex(text)
        text = self._replace_algorithms_with_fenced_latex(text)
        text = self._replace_misc_latex_blocks(text)
        text = self._replace_display_math(text)
        protected: dict[str, str] = {}
        text = self._protect_special_blocks(text, protected)
        text = self._convert_latex_text_with_pandoc(text)
        text = self._normalize_pandoc_markdown(text)
        text = self._replace_lists(text)
        text = self._replace_citations(text)
        text = self._replace_refs(text)
        text = self._replace_simple_text_commands(text)
        text = self._remove_layout_commands(text)
        text = re.sub(r"\\label\{[^{}]*\}", "", text)
        text = re.sub(r"\\(?:paragraph|subparagraph)\*?\{([^{}]+)\}", r"**\1.**", text)
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", text)
        text = self._restore_special_blocks(text, protected)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = self._reflow_markdown_paragraphs(text)
        return text.strip()

    def _convert_latex_text_with_pandoc(self, text: str) -> str:
        """Use Pandoc for ordinary LaTeX-to-Markdown conversion when available."""
        try:
            import pypandoc
        except ImportError:
            return text
        try:
            return pypandoc.convert_text(
                text,
                to=PANDOC_MARKDOWN_FORMAT,
                format="latex",
                extra_args=["--wrap=none"],
            )
        except Exception as exc:
            self.warnings.append(f"pandoc markdown conversion failed; used fallback rules: {exc}")
            return text

    def _normalize_pandoc_markdown(self, text: str) -> str:
        text = re.sub(r"^\[\]\{#[^}\n]+\}\n+", "", text, flags=re.MULTILINE)
        text = re.sub(
            r"\[\\?\[?([^\]\[]+)\\?\]?\]\(#[^)]+\)\{reference-type=\"ref\" reference=\"([^\"]+)\"\}",
            lambda match: match.group(2),
            text,
        )
        text = re.sub(
            r"\[((?:@[A-Za-z0-9:_\-./]+(?:;\s*)?)+)\]",
            lambda match: "[" + ", ".join(key.strip().lstrip("@") for key in match.group(1).split(";")) + "]",
            text,
        )
        text = re.sub(r"<span class=\"citation\" data-cites=\"([^\"]+)\"></span>", lambda m: "[" + m.group(1) + "]", text)
        return text

    def _replace_figures_with_markdown(self, text: str, figure_links: dict[str, str]) -> str:
        pattern = re.compile(
            r"\\begin\{(?P<env>figure\*?|wrapfigure)\}(?P<body>.*?)\\end\{(?P=env)\}",
            flags=re.DOTALL | re.IGNORECASE,
        )

        def repl(match: re.Match[str]) -> str:
            body = match.group("body")
            caption = self._first_caption(body)
            label = self._first_label(body)
            graphics = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", body)
            lines: list[str] = []
            for graphic in graphics:
                graphic = graphic.strip()
                target = figure_links.get(graphic) or figure_links.get(label) or graphic
                alt = caption or label or Path(graphic).stem
                lines.append(f"![{alt}]({target})")
            if caption:
                lines.append(f"*Figure: {caption}*")
            return "\n\n".join(lines)

        return pattern.sub(repl, text)

    def _replace_tables_with_fenced_latex(self, text: str) -> str:
        pattern = re.compile(
            r"\\begin\{(?P<env>table\*?|wraptable)\}"
            r"(?P<head>(?:\[[^\]]*\]|\{[^{}]*\})*)"
            r"(?P<body>.*?)"
            r"\\end\{(?P=env)\}",
            re.DOTALL | re.IGNORECASE,
        )

        def repl(match: re.Match[str]) -> str:
            env = match.group("env")
            head = match.group("head") or ""
            body = match.group("body").strip()
            caption = self._first_caption(body)
            header = f"**Table: {caption}**\n\n" if caption else "**Table:**\n\n"
            raw = f"\\begin{{{env}}}{head}\n{body}\n\\end{{{env}}}"
            return f"{header}```latex\n{raw}\n```"

        return pattern.sub(repl, text)

    def _replace_algorithms_with_fenced_latex(self, text: str) -> str:
        pattern = re.compile(
            r"\\begin\{(?P<env>algorithm\*?|algorithmic)\}(?P<body>.*?)\\end\{(?P=env)\}",
            re.DOTALL | re.IGNORECASE,
        )

        def repl(match: re.Match[str]) -> str:
            body = match.group("body").strip()
            caption = self._first_caption(body)
            header = f"**Algorithm: {caption}**\n\n" if caption else "**Algorithm:**\n\n"
            return f"{header}```latex\n{body}\n```"

        return pattern.sub(repl, text)

    def _replace_misc_latex_blocks(self, text: str) -> str:
        """Fence complex LaTeX blocks that do not have a faithful Markdown form."""
        pattern = re.compile(
            r"\\begin\{(?P<env>lstlisting|tcolorbox|longtable|tabularx?|verbatim|minted)\}"
            r"(?P<head>(?:\[[^\]]*\]|\{[^{}]*\})*)"
            r"(?P<body>.*?)"
            r"\\end\{(?P=env)\}",
            re.DOTALL | re.IGNORECASE,
        )

        def repl(match: re.Match[str]) -> str:
            env = match.group("env")
            head = match.group("head") or ""
            body = match.group("body").strip()
            raw = f"\\begin{{{env}}}{head}\n{body}\n\\end{{{env}}}"
            return f"**LaTeX block: {env}**\n\n```latex\n{raw}\n```"

        parts = re.split(r"(```latex\n.*?\n```)", text, flags=re.DOTALL)
        return "".join(part if part.startswith("```latex") else pattern.sub(repl, part) for part in parts)

    def _replace_display_math(self, text: str) -> str:
        envs = "equation\\*?|align\\*?|aligned|gather\\*?|multline\\*?"
        text = re.sub(
            rf"\\begin\{{(?P<env>{envs})\}}(?P<body>.*?)\\end\{{(?P=env)\}}",
            lambda m: "\n$$\n" + m.group("body").strip() + "\n$$\n",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"\\\[(.*?)\\\]", lambda m: "\n$$\n" + m.group(1).strip() + "\n$$\n", text, flags=re.DOTALL)
        text = re.sub(r"\\\((.*?)\\\)", lambda m: "$" + m.group(1).strip() + "$", text, flags=re.DOTALL)
        return text

    def _replace_lists(self, text: str) -> str:
        text = re.sub(
            r"\\begin\{(?P<env>itemize|enumerate)\}(?:\[[^\]]*\])?(?P<body>.*?)\\end\{(?P=env)\}",
            self._list_repl,
            text,
            flags=re.DOTALL,
        )
        return text

    def _list_repl(self, match: re.Match[str]) -> str:
        body = match.group("body")
        chunks = re.split(r"\\item(?:\[[^\]]*\])?", body)
        items = [item.strip() for item in chunks[1:] if item.strip()]
        return "\n".join(f"- {item}" for item in items)

    def _replace_citations(self, text: str) -> str:
        return re.sub(
            r"\\cite[tpa]?\*?(?:\[[^\]]*\]){0,2}\{([^{}]+)\}",
            lambda m: "[" + ", ".join(key.strip() for key in m.group(1).split(",")) + "]",
            text,
        )

    def _replace_refs(self, text: str) -> str:
        text = re.sub(r"\\(?:autoref|cref|Cref|ref|eqref)\{([^{}]+)\}", r"\1", text)
        text = re.sub(r"~+", " ", text)
        return text

    def _replace_simple_text_commands(self, text: str) -> str:
        replacements = {
            "textbf": r"**\1**",
            "textit": r"*\1*",
            "emph": r"*\1*",
            "texttt": r"`\1`",
            "underline": r"\1",
        }
        for command, repl in replacements.items():
            text = re.sub(rf"\\{command}\{{([^{{}}]*)\}}", repl, text)
        text = re.sub(r"\\url\{([^{}]+)\}", r"\1", text)
        text = re.sub(r"\\href\{([^{}]+)\}\{([^{}]+)\}", r"[\2](\1)", text)
        return text

    def _remove_layout_commands(self, text: str) -> str:
        return re.sub(
            r"\\(?:vspace|hspace|setlength|addtolength|centering|small|footnotesize|scriptsize|resizebox|scalebox)\*?(?:\[[^\]]*\])?(?:\{[^{}]*\}){0,3}",
            " ",
            text,
        )

    def _protect_special_blocks(self, text: str, protected: dict[str, str]) -> str:
        patterns = [
            r"\*\*(?:Table|Algorithm|LaTeX block):.*?\*\*\n\n```latex\n.*?\n```",
            r"```latex\n.*?\n```",
            r"!\[[^\]]*\]\([^)]+\)",
            r"\*Figure:.*?\*",
            r"\$\$.*?\$\$",
            r"\$(?!\$).*?(?<!\$)\$",
        ]
        for pattern in patterns:
            text = re.sub(pattern, lambda m: self._store_protected(m.group(0), protected), text, flags=re.DOTALL)
        return text

    def _store_protected(self, value: str, protected: dict[str, str]) -> str:
        key = f"XXPROTECTED{len(protected)}XX"
        protected[key] = value
        return key

    def _restore_special_blocks(self, text: str, protected: dict[str, str]) -> str:
        for key, value in protected.items():
            text = text.replace(key, value)
        return text

    def _reflow_markdown_paragraphs(self, text: str) -> str:
        """Join source hard-wraps inside prose while preserving Markdown block structure."""
        blocks = self._markdown_blocks(text)
        rendered: list[str] = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                continue
            if self._is_preserved_markdown_block(stripped):
                rendered.append(stripped)
                continue
            if "\n- " in "\n" + stripped:
                rendered.append(self._reflow_list_block(stripped))
                continue
            rendered.append(re.sub(r"\s*\n\s*", " ", stripped))
        return "\n\n".join(rendered)

    def _markdown_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        current: list[str] = []
        in_fence = False
        in_math = False
        for line in text.strip().splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                current.append(line.rstrip())
                in_fence = not in_fence
                continue
            if stripped == "$$":
                current.append(line.rstrip())
                in_math = not in_math
                continue
            if not stripped and not in_fence and not in_math:
                if current:
                    blocks.append("\n".join(current))
                    current = []
                continue
            current.append(line.rstrip())
        if current:
            blocks.append("\n".join(current))
        return blocks

    def _is_preserved_markdown_block(self, block: str) -> bool:
        first = block.splitlines()[0].lstrip()
        return first.startswith(
            (
                "#",
                "![",
                "```",
                "$$",
                "*Figure:",
                "**Table:",
                "**Algorithm:",
            )
        )

    def _reflow_list_block(self, block: str) -> str:
        items: list[str] = []
        current: list[str] = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                if current:
                    items.append(" ".join(current).strip())
                current = [stripped]
            elif current:
                current.append(stripped)
            elif stripped:
                items.append(stripped)
        if current:
            items.append(" ".join(current).strip())
        return "\n".join(items)

    def _figure_links(self, figures: list[FigureAsset]) -> dict[str, str]:
        links: dict[str, str] = {}
        for figure in figures:
            if not figure.asset_path:
                continue
            markdown_path = figure.asset_path.removeprefix("assets/")
            if figure.source_path:
                links.setdefault(figure.source_path, markdown_path)
            if figure.label:
                links.setdefault(figure.label, markdown_path)
        return links

    def _source_file_hashes(self, paper_dir: Path) -> list[SourceFileHash]:
        source_files = []
        for rel in self.parser._source_files:
            path = paper_dir / rel
            if not path.is_file():
                continue
            source_files.append(SourceFileHash(path=rel, sha256=self._sha256(path), bytes=path.stat().st_size))
        return source_files

    def _write_json(self, path: Path, payload: dict) -> None:
        self._ensure_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        self._ensure_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _ensure_output_path(self, path: Path) -> None:
        artifacts_dir = self.settings.resolved_artifacts_dir()
        path.resolve().relative_to(artifacts_dir)

    def _resolve_graphic_path(self, graphic: str, paper_dir: Path) -> Path | None:
        raw = Path(graphic)
        candidates = [raw]
        if raw.suffix == "":
            candidates.extend(Path(str(raw) + suffix) for suffix in sorted(IMAGE_SUFFIXES | UNSUPPORTED_IMAGE_SUFFIXES))
        for candidate in candidates:
            exact = paper_dir / candidate
            if exact.is_file():
                return exact.resolve()
            case_resolved = find_file_case_insensitive(paper_dir, candidate)
            if case_resolved is not None:
                return case_resolved.resolve()
        filename_matches = [path for path in paper_dir.rglob(raw.name) if path.is_file()]
        if filename_matches:
            return filename_matches[0].resolve()
        return None

    def _materialize_figure(self, source: Path, output_path: Path) -> str:
        suffix = source.suffix.lower()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if suffix == ".pdf":
            convert_pdf_first_page_to_jpg(source, output_path.with_suffix(".jpg"))
            if output_path.suffix.lower() != ".jpg":
                output_path = output_path.with_suffix(".jpg")
            return "rendered"
        if suffix in {".png", ".jpg", ".jpeg"}:
            shutil.copy2(source, output_path)
            return "copied"
        if suffix in UNSUPPORTED_IMAGE_SUFFIXES:
            return "unsupported"
        return "unsupported"

    def _unique_figure_name(self, figure_id: str, source: Path, used_names: set[str]) -> str:
        suffix = ".jpg" if source.suffix.lower() == ".pdf" else source.suffix.lower()
        base = self._slugify_id(figure_id).replace("fig-", "", 1) or source.stem
        candidate = f"{base}{suffix}"
        index = 2
        while candidate in used_names:
            candidate = f"{base}-{index}{suffix}"
            index += 1
        used_names.add(candidate)
        return candidate

    def _section_for_offset(self, _text: str, _offset: int, sections: list[SectionAsset]) -> str:
        return sections[0].id if sections else ""

    def _bib_entries(self, text: str) -> list[str]:
        entries: list[str] = []
        index = 0
        while True:
            start = text.find("@", index)
            if start < 0:
                break
            brace = text.find("{", start)
            if brace < 0:
                break
            depth = 0
            end = brace
            while end < len(text):
                char = text[end]
                if char == "{" and (end == 0 or text[end - 1] != "\\"):
                    depth += 1
                elif char == "}" and (end == 0 or text[end - 1] != "\\"):
                    depth -= 1
                    if depth == 0:
                        end += 1
                        break
                end += 1
            entries.append(text[start:end])
            index = end
        return entries

    def _bib_fields(self, raw_entry: str) -> dict[str, str]:
        body = raw_entry.split(",", 1)[1] if "," in raw_entry else ""
        fields: dict[str, str] = {}
        pattern = re.compile(r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)", re.DOTALL)
        for match in pattern.finditer(body):
            key = match.group(1).lower()
            value = match.group(2).strip().strip(",")
            if (value.startswith("{") and value.endswith("}")) or (value.startswith('"') and value.endswith('"')):
                value = value[1:-1]
            fields[key] = re.sub(r"\s+", " ", value).strip()
        return fields

    def _split_authors(self, author_field: str) -> list[str]:
        if not author_field:
            return []
        return [self.parser._clean_inline_latex(part).strip() for part in re.split(r"\s+and\s+", author_field) if part.strip()]

    def _parse_year(self, value: str) -> int | None:
        match = re.search(r"(19|20)\d{2}", value)
        return int(match.group(0)) if match else None

    def _arxiv_id(self, value: str) -> str:
        match = re.search(r"\d{4}\.\d{4,5}(?:v\d+)?", value)
        return match.group(0) if match else ""

    def _first_caption(self, body: str) -> str:
        captions = re.findall(r"\\caption(?:\[[^\]]*\])?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", body)
        return self.parser._clean_inline_latex(captions[0]) if captions else ""

    def _first_label(self, body: str) -> str:
        match = re.search(r"\\label\{([^{}]+)\}", body)
        return match.group(1).strip() if match else ""

    def _labels(self, text: str) -> list[str]:
        return sorted(set(label.strip() for label in re.findall(r"\\label\{([^{}]+)\}", text) if label.strip()))

    def _citations(self, text: str) -> list[str]:
        keys: list[str] = []
        for group in re.findall(r"\\cite[tpa]?\*?(?:\[[^\]]*\]){0,2}\{([^{}]+)\}", text):
            keys.extend(key.strip() for key in group.split(",") if key.strip())
        return sorted(set(keys))

    def _compact_context(self, text: str, limit: int = 300) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        return compact[:limit].rsplit(" ", 1)[0] if len(compact) > limit else compact

    def _figure_id(self, label: str, graphic: str, env_index: int, graphic_index: int) -> str:
        if label:
            return self._slugify_id(label)
        stem = Path(graphic).stem or f"{env_index}-{graphic_index}"
        return self._slugify_id(f"fig-{stem}-{env_index}-{graphic_index}")

    def _unique_id(self, base: str, used_ids: set[str]) -> str:
        candidate = base
        index = 2
        while candidate in used_ids:
            candidate = f"{base}-{index}"
            index += 1
        used_ids.add(candidate)
        return candidate

    def _slugify_id(self, value: str) -> str:
        value = value.lower().replace(":", "-")
        value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
        return value or "item"

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _validate_slug(self, slug: str) -> None:
        validate_slug(slug)
