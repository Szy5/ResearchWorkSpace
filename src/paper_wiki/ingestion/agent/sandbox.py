"""Read-only folder sandbox for a single paper (raw-source-first).

Prioritizes Layer 0 ``raw/`` LaTeX / BibTeX sources directly as the primary
reading environment so the agent never loses information to lossy Markdown
conversion, while still exposing ``assets/`` (and converted ``assets/figures/``
paths in the initial map) as secondary reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from paper_wiki.assets.models import PaperAssetsBundle
from paper_wiki.ingestion.generators.summary_context import main_body_figures

READABLE_TEXT_EXTENSIONS = frozenset(
    {
        ".tex",
        ".bib",
        ".bbl",
        ".md",
        ".txt",
        ".json",
        ".csv",
        ".tsv",
        ".yaml",
        ".yml",
        ".py",
        ".sh",
    }
)
IGNORED_DIR_NAMES = frozenset({"__pycache__", ".git", ".pytest_cache"})
MAX_GREP_LINE_CHARS = 300
MAX_RAW_OUTLINE_ITEMS = 80

_TEX_SECTION_RE = re.compile(r"\\(sub)?section\*?(?:\[[^\]]*\])?\{([^}]{1,140})\}")
_TEX_INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]{1,140})\}")


@dataclass(frozen=True)
class SandboxFileInfo:
    """Metadata for one readable text file inside the paper sandbox."""

    virtual_path: str
    real_path: Path
    size_bytes: int
    line_count: int


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "列出当前论文文件夹内可读文本文件及其行数和字节大小。"
                "默认优先列出 raw/ 下的原始 LaTeX/BibTeX 源文件（主读区），也可传 all 或 assets。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["raw", "all", "assets"],
                        "description": "限定列出范围，默认 raw。",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_lines",
            "description": (
                "按行号读取指定文件片段（1-indexed，闭区间），适合替代 head/tail/sed。"
                "单次调用受最大行数与字符上限保护，可并行调用多次以一次读取多个 .tex 章节或表格文件。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "虚拟相对路径，例如 raw/main.tex、raw/tables/main_res.tex 或 raw/appendix.tex。",
                    },
                    "start_line": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "起始行号（从 1 开始，含）。",
                    },
                    "end_line": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "结束行号（含）；省略则从 start_line 起读取默认最大行数。",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_files",
            "description": (
                "在单篇论文文件夹内按正则表达式搜索关键词，返回 文件:行号:上下文 片段。"
                "默认直接搜索 raw/ 原始源码目录，适合精准定位表格、消融实验、附录、超参数、局限或参考文献。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "正则表达式或关键词（例如 ablation|limitation|Table|\\\\caption）。",
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "可选：限定搜索单个文件或前缀目录（例如 raw/main.tex、raw/tables、raw、assets、all）。"
                            "默认搜索 raw/。"
                        ),
                    },
                    "context_lines": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 5,
                        "description": "每条命中前后附带的上下文行数，默认 2。",
                    },
                    "ignore_case": {
                        "type": "boolean",
                        "description": "是否忽略大小写，默认 true。",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]


class PaperSandbox:
    """Strictly read-only virtual filesystem scoped to a single paper's folders."""

    def __init__(
        self,
        raw_dir: Path,
        artifact_dir: Path,
        *,
        max_read_lines: int = 150,
        max_read_chars: int = 8000,
        max_grep_matches: int = 25,
    ) -> None:
        self.raw_dir = raw_dir.resolve()
        self.assets_dir = (artifact_dir / "assets").resolve()
        self.max_read_lines = max(10, max_read_lines)
        self.max_read_chars = max(500, max_read_chars)
        self.max_grep_matches = max(1, max_grep_matches)

    def dispatch(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute one tool call and always return a model-readable string."""
        try:
            if tool_name == "list_files":
                return self.list_files(scope=str(args.get("scope", "raw")))
            if tool_name == "read_lines":
                path = args.get("path")
                if not isinstance(path, str) or not path.strip():
                    return "Error: 'path' is required for read_lines."
                start_line = int(args.get("start_line", 1))
                raw_end = args.get("end_line")
                end_line = int(raw_end) if raw_end is not None else None
                return self.read_lines(path=path, start_line=start_line, end_line=end_line)
            if tool_name == "grep_files":
                pattern = args.get("pattern")
                if not isinstance(pattern, str) or not pattern.strip():
                    return "Error: 'pattern' is required for grep_files."
                path = args.get("path")
                context_lines = int(args.get("context_lines", 2))
                ignore_case = bool(args.get("ignore_case", True))
                return self.grep_files(
                    pattern=pattern,
                    path=str(path) if isinstance(path, str) and path.strip() else None,
                    context_lines=context_lines,
                    ignore_case=ignore_case,
                )
            return f"Error: Unknown tool '{tool_name}'. Available tools: list_files, read_lines, grep_files."
        except Exception as exc:
            return f"Error executing {tool_name}: {exc}"

    def list_files(self, scope: str = "raw") -> str:
        """List readable text files under raw/ and/or assets/."""
        normalized = scope.strip().lower()
        if normalized not in {"raw", "all", "assets"}:
            return "Error: scope must be one of 'raw', 'all', 'assets'."

        files = self._collect_files(normalized)
        if not files:
            return f"No readable text files found in scope='{normalized}'."

        lines = [f"Readable files (scope={normalized}, count={len(files)}):"]
        for item in files:
            lines.append(f"- {item.virtual_path} ({item.line_count} lines, {item.size_bytes} bytes)")
        return "\n".join(lines)

    def read_lines(self, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Read a bounded 1-indexed inclusive slice of a file inside the sandbox."""
        virtual_path, real_path = self._resolve_file(path)
        if not real_path.is_file():
            return f"Error: File not found: {virtual_path}. Call list_files() to see valid paths."

        all_lines = self._read_text_lines(real_path)
        total = len(all_lines)
        if total == 0:
            return f"[{virtual_path}] (empty file, 0 lines)"

        start = max(1, start_line)
        if start > total:
            return f"[{virtual_path}] start_line={start} exceeds total lines ({total})."

        requested_end = total if end_line is None else max(start, end_line)
        capped_end = min(total, requested_end, start + self.max_read_lines - 1)

        out_lines: list[str] = []
        used_chars = 0
        actual_end = start - 1
        truncated_by_chars = False
        for line_no in range(start, capped_end + 1):
            formatted = f"L{line_no}: {all_lines[line_no - 1]}"
            if out_lines and used_chars + len(formatted) + 1 > self.max_read_chars:
                truncated_by_chars = True
                break
            out_lines.append(formatted)
            used_chars += len(formatted) + 1
            actual_end = line_no

        header = f"[{virtual_path}] lines {start}-{actual_end} / {total}"
        notes: list[str] = []
        if truncated_by_chars or actual_end < min(total, requested_end):
            notes.append(f"truncated by limit; call read_lines(path='{virtual_path}', start_line={actual_end + 1}) for more")
        elif actual_end < total:
            notes.append(f"remaining lines: {actual_end + 1}-{total}")
        footer = f"\n[Note: {'; '.join(notes)}]" if notes else ""
        return f"{header}\n" + "\n".join(out_lines) + footer

    def grep_files(
        self,
        pattern: str,
        path: str | None = None,
        context_lines: int = 2,
        ignore_case: bool = True,
    ) -> str:
        """Regex search across readable files inside the sandbox (defaults to raw/)."""
        ctx = max(0, min(context_lines, 5))
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return f"Error: Invalid regex '{pattern}': {exc}. Retry with a valid regex or simpler keyword."

        targets = self._resolve_grep_targets(path)
        if not targets:
            return f"No readable text files matched path='{path or 'raw'}'. Call list_files() to check available paths."

        blocks: list[str] = []
        match_count = 0
        hit_limit = False

        for item in targets:
            lines = self._read_text_lines(item.real_path)
            for idx, line in enumerate(lines):
                if not regex.search(line):
                    continue
                match_count += 1
                if match_count > self.max_grep_matches:
                    hit_limit = True
                    break
                lo = max(0, idx - ctx)
                hi = min(len(lines) - 1, idx + ctx)
                snippet = [f"--- {item.virtual_path}:L{idx + 1} ---"]
                for pos in range(lo, hi + 1):
                    marker = ">" if pos == idx else " "
                    clipped = lines[pos]
                    if len(clipped) > MAX_GREP_LINE_CHARS:
                        clipped = clipped[:MAX_GREP_LINE_CHARS] + "…"
                    snippet.append(f"{marker} L{pos + 1}: {clipped}")
                blocks.append("\n".join(snippet))
            if hit_limit:
                break

        if not blocks:
            return f"No matches for pattern '{pattern}' in '{path or 'raw'}'."

        summary = f"Matches for '{pattern}' (shown={len(blocks)}" + (
            f", truncated at max {self.max_grep_matches}; narrow pattern or path)" if hit_limit else ")"
        )
        return summary + "\n\n" + "\n\n".join(blocks)

    def raw_source_stats(self) -> tuple[int, int]:
        """Return ``(file_count, total_tex_bytes)`` for raw source files."""
        raw_files = self._collect_files("raw")
        tex_bytes = sum(item.size_bytes for item in raw_files if item.real_path.suffix.lower() == ".tex")
        return len(raw_files), tex_bytes

    def build_initial_map(self, bundle: PaperAssetsBundle) -> str:
        """Build a compact Turn-0 map centered on raw/ LaTeX sources plus figure paths."""
        raw_files = self._collect_files("raw")
        entry_hint = f"raw/{bundle.entry_file}" if bundle.entry_file else "未识别（请查看下方 raw/ 文件清单）"

        parts: list[str] = [
            f"# 论文源码环境地图：{bundle.title}",
            "",
            f"- Slug: `{bundle.slug}`",
            f"- Authors: {', '.join(bundle.authors[:12]) if bundle.authors else '未知'}",
            f"- 推测主入口文件: `{entry_hint}`",
            f"- raw/ 可读源文件数: {len(raw_files)}",
        ]

        if bundle.abstract.strip():
            parts.extend(["", "## Abstract", "", bundle.abstract.strip()])

        parts.extend(["", "## 原始源码文件清单（raw/，优先直接阅读）", "", self.list_files("raw")])

        raw_outline = self._build_raw_tex_outline(raw_files, entry_file=bundle.entry_file)
        if raw_outline:
            parts.extend(["", "## 源码章节与 \\input 结构索引（raw/*.tex 行号参考）", "", *raw_outline])

        figures = main_body_figures(bundle)
        if figures:
            fig_lines = [
                f"- [FIGURE] path: {path} | 所在章节: {where or '未知'} | 原图注: {caption or '无'}"
                for path, where, caption in figures
            ]
            parts.extend(["", "## 可用配图（插图只能使用这里列出的 path）", "", *fig_lines])
        else:
            parts.extend(["", "## 可用配图", "", "（本文没有可用的配图，正文中不要插入任何图片。）"])

        return "\n".join(parts).strip() + "\n"

    def _build_raw_tex_outline(self, raw_files: list[SandboxFileInfo], *, entry_file: str = "") -> list[str]:
        """Deterministically scan raw .tex files for \\section / \\subsection / \\input lines."""
        tex_files = [item for item in raw_files if item.real_path.suffix.lower() == ".tex"]
        entry_virtual = f"raw/{entry_file}" if entry_file else ""
        tex_files.sort(key=lambda item: (0 if item.virtual_path == entry_virtual else 1, item.virtual_path))

        outline: list[str] = []
        for item in tex_files:
            lines = self._read_text_lines(item.real_path)
            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("%"):
                    continue
                if sec := _TEX_SECTION_RE.search(stripped):
                    prefix = "  - subsec" if sec.group(1) else "- sec"
                    title = re.sub(r"\s+", " ", sec.group(2)).strip()
                    outline.append(f"{prefix} `{item.virtual_path}:L{idx}`: {title}")
                elif inp := _TEX_INPUT_RE.search(stripped):
                    target = inp.group(1).strip()
                    outline.append(f"  - input `{item.virtual_path}:L{idx}` -> `{target}`")
                if len(outline) >= MAX_RAW_OUTLINE_ITEMS:
                    outline.append(f"... (已截断，仅展示前 {MAX_RAW_OUTLINE_ITEMS} 条；其余请用 grep_files 检索)")
                    return outline
        return outline

    def _collect_files(self, scope: str) -> list[SandboxFileInfo]:
        roots: list[tuple[str, Path]] = []
        if scope in {"raw", "all"} and self.raw_dir.is_dir():
            roots.append(("raw", self.raw_dir))
        if scope in {"all", "assets"} and self.assets_dir.is_dir():
            roots.append(("assets", self.assets_dir))

        collected: list[SandboxFileInfo] = []
        for prefix, root in roots:
            for candidate in sorted(root.rglob("*")):
                if not candidate.is_file():
                    continue
                if any(part.startswith(".") or part in IGNORED_DIR_NAMES for part in candidate.relative_to(root).parts):
                    continue
                if candidate.suffix.lower() not in READABLE_TEXT_EXTENSIONS:
                    continue
                try:
                    resolved = candidate.resolve()
                    resolved.relative_to(root)
                except ValueError:
                    continue
                rel = resolved.relative_to(root).as_posix()
                lines = self._read_text_lines(resolved)
                collected.append(
                    SandboxFileInfo(
                        virtual_path=f"{prefix}/{rel}",
                        real_path=resolved,
                        size_bytes=resolved.stat().st_size,
                        line_count=len(lines),
                    )
                )
        return collected

    def _resolve_file(self, raw_path: str) -> tuple[str, Path]:
        normalized = raw_path.strip().replace("\\", "/").lstrip("./")
        if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
            raise ValueError(f"Invalid sandbox path (must stay inside raw/ or assets/): {raw_path}")

        if normalized.startswith("raw/"):
            root = self.raw_dir
            rel = normalized.removeprefix("raw/")
        elif normalized.startswith("assets/"):
            root = self.assets_dir
            rel = normalized.removeprefix("assets/")
        else:
            raise ValueError(f"Path must start with 'raw/' or 'assets/': {raw_path}")

        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Path escapes sandbox root: {raw_path}") from exc
        return normalized, candidate

    def _resolve_grep_targets(self, path: str | None) -> list[SandboxFileInfo]:
        if path is None or path.strip().lower() in {"", "raw"}:
            raw_files = self._collect_files("raw")
            return raw_files if raw_files else self._collect_files("assets")
        cleaned = path.strip().replace("\\", "/").lstrip("./").rstrip("/")
        lowered = cleaned.lower()
        if lowered in {"all", "assets"}:
            return self._collect_files(lowered)

        virtual_path, resolved = self._resolve_file(cleaned)
        if resolved.is_file():
            if resolved.suffix.lower() not in READABLE_TEXT_EXTENSIONS:
                return []
            lines = self._read_text_lines(resolved)
            return [
                SandboxFileInfo(
                    virtual_path=virtual_path,
                    real_path=resolved,
                    size_bytes=resolved.stat().st_size,
                    line_count=len(lines),
                )
            ]
        if resolved.is_dir():
            prefix = "raw" if virtual_path.startswith("raw/") else "assets"
            return [item for item in self._collect_files(prefix) if item.virtual_path.startswith(virtual_path + "/")]
        return []

    def _read_text_lines(self, path: Path) -> list[str]:
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
