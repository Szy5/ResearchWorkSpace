from __future__ import annotations

import logging
import re
from pathlib import Path

from paper_wiki.assets.models import PaperAssetsBundle
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path

logger = logging.getLogger(__name__)


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

        prompt_path = resolve_prompt_path(self.prompts_dir, prompt_file or "paper_summary.py")
        prompt_vars = load_prompt_module(prompt_path)
        system = prompt_vars["paper_summary_system_prompt"].strip()
        user_template = prompt_vars["paper_summary_user_prompt"]
        user = user_template.replace("{PAPER_TITLE}", bundle.title).replace(
            "{PAPER_CONTENT}",
            bundle.llm_context(max_chars=self.max_context_chars),
        )

        content = self.llm.complete(system, user).strip()
        content = self._rewrite_figure_paths(content, bundle)
        summary = self._clean_summary_content(content)
        logger.info("summary.md 生成完成：slug=%s, chars=%d", bundle.slug, len(summary))
        return summary

    def _clean_summary_content(self, content: str) -> str:
        """删除模型可能生成的 frontmatter，保持 summary.md 只包含正文。"""
        content = self._strip_outer_fence(content.strip())
        body = self._strip_existing_frontmatter(content)
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
