from __future__ import annotations

import logging
import re
from pathlib import Path

from paper_wiki.core.models import ParsedPaper

logger = logging.getLogger(__name__)


TARGET_SECTIONS: dict[str, list[str]] = {
    "introduction": ["introduction", "motivation", "overview"],
    "related_work": ["related work", "background", "prior work", "literature review", "related"],
    "method": [
        "method",
        "approach",
        "model",
        "framework",
        "proposed",
        "our method",
        "methodology",
        "technique",
        "algorithm",
    ],
    "experiments": ["experiment", "evaluation", "result", "empirical", "analysis", "benchmark"],
}

# 给 LLM 的正文顺序：先给摘要和主张相关章节，再给实验与相关工作。
# 这样在截断时能优先保留最影响语义产物质量的信息。
ASSEMBLY_ORDER = ["abstract", "introduction", "method", "related_work", "experiments"]


class LaTeXParser:
    """将 raw/{slug}/ 中的 LaTeX 源码整理成适合 LLM 消费的论文文本。"""

    def __init__(self, max_chars: int = 4000) -> None:
        self.max_chars = max_chars
        self._source_files: list[str] = []

    def parse(self, paper_dir: Path) -> ParsedPaper:
        """
        解析单篇论文目录，返回正文、元数据、命中章节和实际读取的源文件。
        """
        paper_dir = paper_dir.resolve()
        logger.info("开始解析 LaTeX 目录：%s", paper_dir)
        if not paper_dir.exists() or not paper_dir.is_dir():
            logger.error("论文目录不存在或不是目录：%s", paper_dir)
            raise FileNotFoundError(f"Paper directory does not exist: {paper_dir}")

        # 重置 source_files
        self._source_files = []

        # 1. 定位主文件
        entry = self._find_entry_file(paper_dir)
        logger.info("识别到 LaTeX 入口文件：%s", entry.relative_to(paper_dir))
        # 2. 组成一份完整 LaTeX 文本
        merged = self._inline_inputs(entry, paper_dir)
        
        # 元数据和章节切分需要保留 LaTeX 命令结构，因此这里只先去注释。
        cleaned_for_meta = self._strip_comments(merged)

        title = self._extract_command(cleaned_for_meta, "title")
        authors = self._extract_authors(cleaned_for_meta)
        abstract = self._extract_abstract(cleaned_for_meta)
        sections = self._split_by_section(cleaned_for_meta)
        matched = self._match_target_sections(sections)
        raw_text = self._assemble_and_truncate(abstract, matched, self.max_chars)
        matched_flags = {key: key in matched for key in TARGET_SECTIONS}
        logger.info(
            "LaTeX 解析完成：source_files=%d, estimated_tokens=%d, matched_sections=%s",
            len(self._source_files),
            max(1, int(len(raw_text) / 3.5)),
            matched_flags,
        )
        logger.debug("实际内联文件列表：%s", self._source_files)

        return ParsedPaper(
            slug=paper_dir.name,
            raw_text=raw_text,
            estimated_tokens=max(1, int(len(raw_text) / 3.5)),
            source_files=self._source_files,
            matched_sections=matched_flags,
            title=title or paper_dir.name,
            authors=authors,
            abstract=self._strip_latex_noise(abstract),
            entry_file=str(entry.relative_to(paper_dir)),
        )

    def _find_entry_file(self, paper_dir: Path) -> Path:
        """定位主 tex 文件；优先常见文件名，其次寻找包含 \\begin{document} 的文件。"""
        preferred = ["main.tex", "paper.tex", "article.tex"]
        for name in preferred:
            path = paper_dir / name
            if path.exists():
                logger.debug("使用常见主文件名命中入口：%s", path.name)
                return path

        # 有些论文主文件叫 colm2026_conference.tex / iclr2026_conference.tex；
        # 这类文件通常包含 \begin{document}，比“最大 tex 文件”更可靠。
        tex_files = [p for p in paper_dir.glob("*.tex") if p.is_file()]
        if not tex_files:
            tex_files = [p for p in paper_dir.rglob("*.tex") if p.is_file()]
        if not tex_files:
            raise FileNotFoundError(f"No .tex file found under {paper_dir}")
        document_files = [
            path
            for path in tex_files
            if r"\begin{document}" in path.read_text(encoding="utf-8", errors="ignore")
        ]
        if document_files:
            chosen = max(document_files, key=lambda path: path.stat().st_size)
            logger.debug("使用包含 begin{document} 的文件作为入口：%s", chosen.name)
            return chosen
        chosen = max(tex_files, key=lambda path: path.stat().st_size)
        logger.warning("未找到明确主文件，退化为使用最大 tex 文件：%s", chosen.name)
        return chosen

    def _inline_inputs(
        self,
        tex_path: Path,
        base_dir: Path,
        visited: set[Path] | None = None,
    ) -> str:
        """递归内联 \\input / \\include，组成一份完整 LaTeX 文本。"""
        visited = visited or set()
        tex_path = tex_path.resolve()
        if tex_path in visited:
            # 防止循环 include 导致无限递归。
            logger.warning("跳过循环引用的 LaTeX 文件：%s", tex_path)
            return ""
        visited.add(tex_path)
        self._source_files.append(str(tex_path.relative_to(base_dir)))

        text = tex_path.read_text(encoding="utf-8", errors="ignore")
        pattern = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")

        def replace(match: re.Match[str]) -> str:
            ref = match.group(1).strip()
            child = self._resolve_input_path(ref, tex_path.parent, base_dir)
            if child is None:
                logger.warning("无法解析 LaTeX input/include：ref=%s, current=%s", ref, tex_path)
                return f"\n% Paper-Wiki warning: unresolved input {ref}\n"
            logger.debug("内联 LaTeX 文件：%s -> %s", tex_path.relative_to(base_dir), child.relative_to(base_dir))
            return "\n" + self._inline_inputs(child, base_dir, visited) + "\n"

        return pattern.sub(replace, text)

    def _resolve_input_path(self, ref: str, current_dir: Path, base_dir: Path) -> Path | None:
        """解析 \\input{...} 路径，兼容无 .tex 后缀和相对当前文件的写法。"""
        candidates: list[Path] = []
        raw = Path(ref)
        for root in [current_dir, base_dir]:
            candidate = root / raw
            candidates.append(candidate)
            # 不能用 with_suffix(".tex")：1.introduction 会被误改成 1.tex。
            if not str(candidate).endswith(".tex"):
                candidates.append(Path(str(candidate) + ".tex"))
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return None

    def _split_by_section(self, text: str) -> dict[str, str]:
        """
        按 section/subsection 切分论文文本Chunk，保留标题到下一标题之间的内容。
        """
        heading = re.compile(
            r"\\(?P<level>section|subsection)\*?(?:\[[^\]]*\])?\{(?P<title>[^{}]+)\}",
            flags=re.IGNORECASE,
        )
        matches = list(heading.finditer(text))
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            key = self._clean_inline_latex(match.group("title")).strip()
            if not key:
                continue
            level = match.group("level").lower()
            # subsection 也参与匹配，用于 Related Work 写在 Introduction 子节里的情况。
            section_key = key if level == "section" else f"{key} [subsection]"
            sections[section_key] = text[start:end]
        return sections

    def _match_target_sections(self, sections: dict[str, str]) -> dict[str, str]:
        """
        O(n*n): 通过切分好的Chunk的Title来判断（关键词匹配），当前Chunk属于哪个目标列别，并返回目标列别和Chunk内容。

        1. 命中 \\section 时，会合并其后连续的 \\subsection，除非子节标题明确属于另一个目标类别（例如 Introduction 下的 Related Work）。
        """
        matched: dict[str, str] = {}
        items = list(sections.items())
        consumed: set[int] = set()
        # 遍历切分的所有的论文文本Chunk
        for index, (title, content) in enumerate(items):
            if index in consumed:
                continue

            is_subsection = "[subsection]" in title
            normalized = self._normalize_section_title(title)
            # 通过Chunk Title（normalized）来判断Chunk属于哪个目标类别
            for target, keywords in TARGET_SECTIONS.items():
                if target in matched:
                    continue
                if not any(keyword in normalized for keyword in keywords):
                    continue

                if is_subsection:
                    block = content
                else:
                    block, consumed_indices = self._collect_section_block(items, index, target)
                    consumed.update(consumed_indices)

                matched[target] = self._strip_latex_noise(block)
                break

        return matched

    def _normalize_section_title(self, title: str) -> str:
        return title.lower().replace("_", " ").replace(" [subsection]", "").strip()

    def _match_targets_for_title(self, title: str) -> list[str]:
        normalized = self._normalize_section_title(title)
        return [
            target
            for target, keywords in TARGET_SECTIONS.items()
            if any(keyword in normalized for keyword in keywords)
        ]

    def _collect_section_block(
        self,
        items: list[tuple[str, str]],
        start_index: int,
        parent_target: str,
    ) -> tuple[str, set[int]]:
        """
        合并 section 与其后 subsection。

        默认把子节并入父 section；若子节标题命中且仅命中另一个目标类别，
        则停止合并，留给后续独立匹配（如 Introduction 下的 Related Work）。
        """
        parts = [items[start_index][1]]
        consumed: set[int] = set()

        for index in range(start_index + 1, len(items)):
            child_title, child_content = items[index]
            if "[subsection]" not in child_title:
                break

            child_targets = self._match_targets_for_title(child_title)
            if child_targets and parent_target not in child_targets:
                break

            parts.append(child_content)
            consumed.add(index)

        return "\n\n".join(parts), consumed

    def _extract_abstract(self, text: str) -> str:
        """
        抽取 abstract 环境；没有摘要时返回空字符串，后续 prompt 会降级处理。
        """
        match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return ""
        return self._strip_latex_noise(match.group(1))

    def _strip_latex_noise(self, text: str) -> str:
        """
        清理对 LLM 无帮助的排版命令，同时尽量保留正文、引用线索和 caption。
        """
        text = self._strip_comments(text)
        text = self._replace_float_env_with_captions(text)
        # 在清洗前把 [FIGURE: ...] 标记藏起来，防止路径中的 _ 被 _clean_inline_latex 替换成空格。
        figure_markers: dict[str, str] = {}

        def _hide_figure(m: re.Match) -> str:  # type: ignore[type-arg]
            key = f"XFIGUREX{len(figure_markers)}XFIGUREX"
            figure_markers[key] = m.group(0)
            return key

        text = re.sub(r"\[FIGURE:[^\]]*\]", _hide_figure, text)
        text = re.sub(r"\\(?:vspace|hspace|setlength|addtolength)\*?(?:\[[^\]]*\])?\{[^{}]*\}", " ", text)
        text = re.sub(r"\\label\{[^{}]*\}", " ", text)
        text = re.sub(r"\\ref\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"\\cite[tpa]?\*?(?:\[[^\]]*\]){0,2}\{([^{}]*)\}", r"[\1]", text)
        text = re.sub(r"\\url\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"\\(textit|textbf|emph|texttt|underline)\{([^{}]*)\}", r"\2", text)
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
        text = re.sub(r"[{}]", "", text)
        text = self._clean_inline_latex(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        # 还原 [FIGURE: ...] 标记，路径保持原始形式。
        for key, marker in figure_markers.items():
            text = text.replace(key, marker)
        return text.strip()

    def _replace_float_env_with_captions(self, text: str) -> str:
        """删除大段图表/算法环境，但保留 caption；figure 环境额外保留图片路径供 LLM 引用。"""
        figure_envs = {"figure", "figure*", "wrapfigure"}
        other_envs = ["algorithm", "algorithm*", "lstlisting", "table", "table*"]

        for env in list(figure_envs) + other_envs:
            escaped = re.escape(env)
            pattern = re.compile(rf"\\begin\{{{escaped}\}}(.*?)\\end\{{{escaped}\}}", re.DOTALL | re.IGNORECASE)

            def repl(match: re.Match[str], _env: str = env) -> str:
                body = match.group(1)
                captions = re.findall(r"\\caption(?:\[[^\]]*\])?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", body)
                caption_lines = [f"Caption: {self._clean_inline_latex(c)}" for c in captions]

                if _env in figure_envs:
                    graphic = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", body)
                    label = re.search(r"\\label\{([^{}]+)\}", body)
                    if graphic:
                        path = graphic.group(1)
                        lbl = label.group(1) if label else ""
                        figure_line = f"[FIGURE: {path} | {lbl}]" if lbl else f"[FIGURE: {path}]"
                        return "\n".join([figure_line] + caption_lines)

                return "\n".join(caption_lines)

            text = pattern.sub(repl, text)
        return text

    def _assemble_and_truncate(self, abstract: str, sections: dict[str, str], max_chars: int | None = None) -> str:
        """
        按固定优先级拼接正文；
        超长时保留摘要、引言和方法，裁剪次要部分。
        """
        parts: list[tuple[str, str]] = []
        if abstract:
            parts.append(("Abstract", abstract))
        for key in ASSEMBLY_ORDER[1:]:
            if content := sections.get(key):
                parts.append((key.replace("_", " ").title(), content))

        assembled = "\n\n".join(f"## {title}\n\n{content.strip()}" for title, content in parts if content.strip())
        limit = max_chars or self.max_chars
        if len(assembled) <= limit:
            return assembled

        # 超长论文优先保留“这篇论文要解决什么”和“怎么解决”。
        logger.warning("解析文本超过限制，将按优先级裁剪：chars=%d, limit=%d", len(assembled), limit)
        priority = [("Abstract", abstract), ("Introduction", sections.get("introduction", "")), ("Method", sections.get("method", ""))]
        essential = "\n\n".join(f"## {title}\n\n{content.strip()}" for title, content in priority if content.strip())
        if len(essential) >= limit:
            return essential[:limit].rsplit(" ", 1)[0].strip() + "\n\n[TRUNCATED]"

        remaining = limit - len(essential) - len("\n\n[TRUNCATED]")
        tail = "\n\n".join(
            f"## {title}\n\n{content.strip()}"
            for title, content in [
                ("Related Work", sections.get("related_work", "")),
                ("Experiments", sections.get("experiments", "")),
            ]
            if content.strip()
        )
        return (essential + "\n\n" + tail[:remaining].rsplit(" ", 1)[0].strip() + "\n\n[TRUNCATED]").strip()

    def _extract_command(self, text: str, command: str) -> str:
        """提取 \\title / \\author 这类命令，手动计数花括号以兼容嵌套命令。"""
        match = re.search(rf"\\{command}\s*\{{", text, flags=re.DOTALL)
        if not match:
            return ""
        start = match.end() - 1
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{" and (index == 0 or text[index - 1] != "\\"):
                depth += 1
            elif char == "}" and (index == 0 or text[index - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    return self._clean_inline_latex(text[start + 1 : index])
        return ""

    def _extract_authors(self, text: str) -> list[str]:
        """
        从 author 命令中提取作者名，去掉邮箱、换行后的单位和简单上标编号。
        """
        raw = self._extract_command(text, "author")
        if not raw:
            return []
        raw = re.sub(r"\$.*?\$", "", raw)
        raw = re.sub(r"\\texttt\{.*?\}", "", raw)
        raw = re.split(r"\\\\|\n", raw)[0]
        chunks = re.split(r",|\\and| and ", raw)
        authors = [re.sub(r"\b\d+\b", "", self._clean_inline_latex(chunk)).strip() for chunk in chunks]
        return [author for author in authors if author and not author.startswith("^")]

    def _strip_comments(self, text: str) -> str:
        """去除 LaTeX 注释；保留转义百分号 \\%。"""
        lines = []
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("%"):
                continue
            lines.append(re.sub(r"(?<!\\)%.*$", "", line))
        return "\n".join(lines)

    def _clean_inline_latex(self, text: str) -> str:
        """把简单 inline LaTeX 命令退化为纯文本，作为轻量级预处理。"""
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
        text = re.sub(r"[$^_{}]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
