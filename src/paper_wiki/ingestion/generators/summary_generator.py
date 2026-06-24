from __future__ import annotations

import logging
import re
import runpy
from pathlib import Path

import yaml

from paper_wiki.core.enums import ContributionType
from paper_wiki.core.models import ParsedPaper, SummaryFrontmatter
from paper_wiki.ingestion.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """生成 summary.md，并由本地代码统一写入可信 frontmatter。"""

    def __init__(self, llm: LLMClient, prompts_dir: Path) -> None:
        self.llm = llm
        self.prompts_dir = prompts_dir

    def generate(self, parsed: ParsedPaper) -> str:
        """调用摘要 prompt，再清洗模型输出并补齐 YAML frontmatter。"""
        logger.info("开始生成 summary.md：slug=%s", parsed.slug)
        prompt_vars = runpy.run_path(str(self.prompts_dir / "paper_summary.py"))
        system = prompt_vars["paper_summary_system_prompt"].strip()
        user_template = prompt_vars["paper_summary_user_prompt"]
        user = user_template.replace("{PAPER_TITLE}", parsed.title).replace("{PAPER_CONTENT}", parsed.raw_text)
        user += (
            "\n\n额外要求：输出必须包含 YAML frontmatter，字段至少包括 "
            "slug, title, authors, contribution_type, reviewed, added_date；reviewed 必须为 false。"
        )
        content = self.llm.complete(system, user).strip()
        summary = self._ensure_frontmatter(parsed, content)
        logger.info("summary.md 生成完成：slug=%s, chars=%d", parsed.slug, len(summary))
        return summary

    def _ensure_frontmatter(self, parsed: ParsedPaper, content: str) -> str:
        """忽略模型自带 frontmatter，使用解析器得到的元数据生成权威版本。"""
        content = self._strip_outer_fence(content.strip())
        body = self._strip_existing_frontmatter(content)
        frontmatter = SummaryFrontmatter(
            slug=parsed.slug,
            title=parsed.title,
            authors=parsed.authors,
            contribution_type=self._extract_contribution_type(body),
            reviewed=False,
        )
        yaml_text = yaml.safe_dump(
            frontmatter.model_dump(mode="json", exclude_none=True),
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        return f"---\n{yaml_text}\n---\n\n{body.strip()}\n"

    def _strip_outer_fence(self, content: str) -> str:
        """处理模型把整篇 Markdown 包进代码块的情况。"""
        match = re.fullmatch(r"```(?:markdown|md|yaml|yml)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
        if match:
            logger.debug("检测到模型将 summary 包在代码块中，已剥离外层 fence")
        return match.group(1).strip() if match else content

    def _strip_existing_frontmatter(self, content: str) -> str:
        """删除模型生成的 frontmatter 或伪 frontmatter，避免和本地元数据冲突。"""
        if not content.startswith("---"):
            heading = re.search(r"^#\s+", content, flags=re.MULTILINE)
            if heading and all(key in content[: heading.start()] for key in ["slug:", "title:"]):
                logger.debug("检测到模型生成的伪 frontmatter，已剥离")
                return content[heading.start() :].strip()
            return content
        match = re.match(r"---\s*\n.*?\n---\s*\n?", content, flags=re.DOTALL)
        if not match:
            return content
        logger.debug("检测到模型生成的 frontmatter，已用本地权威 frontmatter 替换")
        return content[match.end() :].strip()

    def _extract_contribution_type(self, content: str) -> ContributionType | None:
        """从正文中识别四类贡献类型，写入 summary frontmatter。"""
        for contribution_type in ContributionType:
            if contribution_type.value in content:
                return contribution_type
        match = re.search(r"\*\*类型\*\*[:：]\s*([^\n]+)", content)
        if not match:
            return None
        value = match.group(1).strip()
        for contribution_type in ContributionType:
            if contribution_type.value in value:
                return contribution_type
        return None
