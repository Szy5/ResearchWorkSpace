from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from paper_wiki.assets.models import PaperAssetsBundle
from paper_wiki.ingestion.generators.summary_context import build_summary_context, main_body_figures
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path

logger = logging.getLogger(__name__)

DEFAULT_SUMMARY_PROMPT = "paper_summary_v5.py"
MIN_SUMMARY_FIGURES = 5

_FIGURE_SUPPLEMENT_SYSTEM = (
    "你是论文速读文章的编辑。笔记里的配图太少，需要从候选图中补充。"
    "只输出 JSON，不要输出其他内容。"
)
_FIGURE_SUPPLEMENT_USER = """笔记目前的小节标题：
{HEADINGS}

尚未使用的候选图（path | 原文章节 | 英文原图注）：
{FIGURES}

请挑选最多 {N} 张最有助于读者理解论文的图（优先方法流程图、主结果图、分析图），为每张图：
- heading：从上面的小节标题中原样选一个最贴切的放置位置：方法图放方法相关小节，实验、消融、训练曲线等分析图放实验/效果相关小节；不要选"论文速览""三句话看懂""值得关注的点""读后小结"这类导读或收尾小节；
- caption：根据原图注写一句中文图注（15~40 字，说明图里展示了什么），不要加"图 N："前缀。

输出格式：{{"placements": [{{"path": "...", "heading": "...", "caption": "..."}}]}}"""


class _FigurePlacement(BaseModel):
    path: str
    heading: str
    caption: str = Field(min_length=1)


class _FigurePlacements(BaseModel):
    placements: list[_FigurePlacement] = Field(default_factory=list)


class SummaryGenerator:
    """生成 summary.md 正文；论文元信息由 manifest.json 维护。"""

    def __init__(self, llm: LLMClient, prompts_dir: Path, max_context_chars: int | None = None) -> None:
        self.llm = llm
        self.prompts_dir = prompts_dir
        self.max_context_chars = max_context_chars

    def generate(self, bundle: PaperAssetsBundle, prompt_file: str | None = None) -> str:
        """
        调用摘要 prompt，再清洗模型输出。
        """

        prompt_path = resolve_prompt_path(self.prompts_dir, prompt_file or DEFAULT_SUMMARY_PROMPT)
        prompt_vars = load_prompt_module(prompt_path)
        system = prompt_vars["paper_summary_system_prompt"].strip()
        user_template = prompt_vars["paper_summary_user_prompt"]
        user = user_template.replace("{PAPER_TITLE}", bundle.title).replace(
            "{PAPER_CONTENT}",
            build_summary_context(bundle, self.max_context_chars),
        )

        content = self.llm.complete(system, user).strip()
        content = self._rewrite_figure_paths(content, bundle)
        summary = self._clean_summary_content(content)
        summary = self._supplement_figures(summary, bundle)
        summary = self._number_figure_captions(summary)
        logger.info("summary.md 生成完成：slug=%s, chars=%d", bundle.slug, len(summary))
        return summary

    def _supplement_figures(self, summary: str, bundle: PaperAssetsBundle) -> str:
        """Ask for placements of unused figures when the draft has too few; insertion itself is deterministic."""
        used = set(re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", summary))
        candidates = [item for item in main_body_figures(bundle) if item[0] not in used]
        missing = min(MIN_SUMMARY_FIGURES, len(used) + len(candidates)) - len(used)
        if missing <= 0:
            return summary
        headings = [
            match.group(2).strip()
            for match in re.finditer(r"^(#{2,3})\s+(.+?)\s*$", summary, flags=re.MULTILINE)
            if "速览" not in match.group(2)
        ]
        if not headings:
            return summary
        user = (
            _FIGURE_SUPPLEMENT_USER.replace("{HEADINGS}", "\n".join(f"- {heading}" for heading in headings))
            .replace("{FIGURES}", "\n".join(f"- {path} | {where or '未知'} | {caption or '无'}" for path, where, caption in candidates))
            .replace("{N}", str(missing))
        )
        try:
            result = self.llm.complete_json(_FIGURE_SUPPLEMENT_SYSTEM, user, _FigurePlacements)
        except Exception as exc:  # supplementing figures is best-effort
            logger.warning("补充配图失败，保留原文：slug=%s, error=%s", bundle.slug, exc)
            return summary

        valid_paths = {path for path, _, _ in candidates}
        added = 0
        for placement in result.placements:
            if added >= missing or placement.path not in valid_paths or placement.path in used:
                continue
            caption = self._CAPTION_PREFIX_RE.sub("", placement.caption.strip()).replace("]", "）").replace("我们", "作者")
            updated = self._insert_at_section_end(summary, placement.heading, f"![{caption}]({placement.path})")
            if updated != summary:
                summary, added = updated, added + 1
                used.add(placement.path)
        if added:
            logger.info("已补充配图：slug=%s, added=%d", bundle.slug, added)
        return summary

    def _insert_at_section_end(self, summary: str, heading: str, block: str) -> str:
        """Insert ``block`` at the end of the section titled ``heading`` (before the next heading)."""
        match = re.search(rf"^#{{2,3}}\s+{re.escape(heading.strip().lstrip('#').strip())}\s*$", summary, flags=re.MULTILINE)
        if not match:
            return summary
        following = re.search(r"^#{1,3}\s", summary[match.end():], flags=re.MULTILINE)
        end = match.end() + following.start() if following else len(summary)
        return f"{summary[:end].rstrip()}\n\n{block}\n\n{summary[end:].lstrip()}".rstrip() + "\n"

    _IMAGE_LINE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)[ \t]*(?:\n(?:[ \t]*\n)?\*{1,2}图\s*\d*\s*[:：]\s*(.+?)\*{1,2}[ \t]*)?$", re.MULTILINE)
    _CAPTION_PREFIX_RE = re.compile(r"^\s*(?:图|Figure|Fig\.?)\s*\d*\s*[:：.]\s*", re.IGNORECASE)

    def _number_figure_captions(self, content: str) -> str:
        """Fold a trailing ``*图：…*`` line into the image alt and number figures 图 1, 图 2… in order."""
        counter = 0

        def repl(match: re.Match[str]) -> str:
            nonlocal counter
            counter += 1
            alt, path, caption = match.group(1), match.group(2), match.group(3)
            text = self._CAPTION_PREFIX_RE.sub("", (caption or alt).strip()).strip() or alt.strip()
            return f"![图 {counter}：{text}]({path})"

        return self._IMAGE_LINE_RE.sub(repl, content)

    def _clean_summary_content(self, content: str) -> str:
        """删除模型可能生成的 frontmatter，保持 summary.md 只包含正文。"""
        content = self._strip_outer_fence(content.strip())
        body = self._strip_existing_frontmatter(content)
        # Markdown only recognises a pipe table that starts after a blank line.
        body = re.sub(r"(?m)^([^|\n][^\n]*)\n(\|)", r"\1\n\n\2", body)
        # The note is written in the third person; models often leak the paper's "we" when translating.
        body = body.replace("我们", "作者")
        return f"{body.strip()}\n"

    def _rewrite_figure_paths(self, content: str, bundle: PaperAssetsBundle) -> str:
        """Rewrite figure links to assets/figures paths relative to summary.md."""
        figure_map = self._figure_path_map(bundle)

        def repl(match: re.Match[str]) -> str:
            alt, path = match.group(1), match.group(2).strip()
            if path.startswith(("http://", "https://", "/")):
                return match.group(0)
            normalized = path.lstrip("./")
            if normalized.startswith("assets/figures/"):
                return f"![{alt}]({normalized})"
            if target := figure_map.get(normalized):
                return f"![{alt}]({target})"
            if target := figure_map.get(Path(normalized).name):
                return f"![{alt}]({target})"
            if normalized.lower().startswith("figures/"):
                return f"![{alt}](assets/{normalized})"
            return match.group(0)

        return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, content)

    def _figure_path_map(self, bundle: PaperAssetsBundle) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for figure in bundle.figures.figures:
            if not figure.asset_path:
                continue
            target = figure.asset_path
            keys = {
                figure.asset_path,
                figure.asset_path.removeprefix("assets/"),
                Path(figure.asset_path).name,
                figure.source_path,
                Path(figure.source_path).name,
            }
            if figure.label:
                keys.add(figure.label)
            for key in keys:
                if key:
                    mapping.setdefault(key, target)
        return mapping

    def _strip_outer_fence(self, content: str) -> str:
        """处理模型把整篇 Markdown 包进代码块的情况。"""
        match = re.fullmatch(r"```(?:markdown|md|yaml|yml)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
        if match:
            logger.debug("检测到模型将 summary 包在代码块中，已剥离外层 fence")
        return match.group(1).strip() if match else content

    def _strip_existing_frontmatter(self, content: str) -> str:
        """删除模型生成的 frontmatter 或伪 frontmatter，避免 summary 重新承载元信息。"""
        if not content.startswith("---"):
            heading = re.search(r"^#\s+", content, flags=re.MULTILINE)
            if heading and all(key in content[: heading.start()] for key in ["slug:", "title:"]):
                logger.debug("检测到模型生成的伪 frontmatter，已剥离")
                return content[heading.start() :].strip()
            return content
        match = re.match(r"---\s*\n.*?\n---\s*\n?", content, flags=re.DOTALL)
        if not match:
            return content
        logger.debug("检测到模型生成的 frontmatter，已剥离")
        return content[match.end() :].strip()
