from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from paper_wiki.assets.models import PaperAssetsBundle
from paper_wiki.core.models import PriorWorkEntry, PriorWorksDoc
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path

logger = logging.getLogger(__name__)


class _PriorWorksLLMResponse(BaseModel):
    """模型原始 JSON 形状；主论文元信息由 manifest.json 维护。"""

    prior_works: list[PriorWorkEntry] = Field(default_factory=list)
    synthesis_narrative: str


class PriorWorksGenerator:
    """生成 prior_works.json，捕捉当前论文直接依赖的前作谱系。"""

    def __init__(self, llm: LLMClient, prompts_dir: Path, max_context_chars: int | None = None) -> None:
        self.llm = llm
        self.prompts_dir = prompts_dir
        self.max_context_chars = max_context_chars

    def generate(self, bundle: PaperAssetsBundle, prompt_file: str | None = None) -> PriorWorksDoc:
        """调用 LLM 识别前作，并用 PriorWorksDoc 做 schema 校验。"""
        logger.info("开始生成 prior_works.json：slug=%s", bundle.slug)
        prompt_path = resolve_prompt_path(self.prompts_dir, prompt_file or "prior_work_prompt.py")
        logger.debug("使用 prior_works prompt：%s", prompt_path)
        prompt_vars = load_prompt_module(prompt_path)
        system = prompt_vars.get("prior_work_system_prompt", "").strip()
        if not system:
            system = prompt_path.read_text(encoding="utf-8", errors="ignore").strip()
        system += "\n\n请严格返回 JSON，不要返回 Markdown。"
        if prompt_file and prompt_vars.get("prior_work_user_prompt"):
            user = self._render_user_prompt(prompt_vars["prior_work_user_prompt"], bundle)
        else:
            user = self._default_user_prompt(bundle)
        # complete_json 会自动处理 JSON fence、格式错误重试和 Pydantic 校验。
        response = self.llm.complete_json(system, user, _PriorWorksLLMResponse)
        doc = PriorWorksDoc(prior_works=response.prior_works, synthesis_narrative=response.synthesis_narrative)
        logger.info("prior_works.json 生成完成：slug=%s, prior_works=%d", bundle.slug, len(doc.prior_works))
        return doc

    def _default_user_prompt(self, bundle: PaperAssetsBundle) -> str:
        return f"""
分析这篇研究论文，并识别直接促成其核心创新的 5-7 篇关键前作。

论文标题：
{bundle.title}

作者：
{", ".join(bundle.authors) if bundle.authors else "未知"}

摘要：
{bundle.abstract or "未提取到摘要"}

论文正文节选：
{bundle.llm_context(max_chars=self.max_context_chars)}

JSON 字段必须为：
{{
  "prior_works": [
    {{
      "title": "准确论文标题",
      "authors": "第一作者 et al.",
      "year": 2023,
      "arxiv_id": "",
      "role": "Baseline|Inspiration|Gap Identification|Foundation|Extension|Related Problem",
      "relationship_sentence": "一句话说明它与当前论文核心创新的直接关系"
    }}
  ],
  "synthesis_narrative": "200-300 词综合叙述"
}}
""".strip()

    def _render_user_prompt(self, template: str, bundle: PaperAssetsBundle) -> str:
        authors = ", ".join(bundle.authors) if bundle.authors else "未知"
        paper_text = bundle.llm_context(max_chars=self.max_context_chars) or "[PDF 提取不可用——请基于标题和摘要进行分析]"
        return (
            template.replace("{paper_metadata['title']}", bundle.title)
            .replace("{', '.join(paper_metadata['authors'])}", authors)
            .replace("{paper_metadata['abstract']}", bundle.abstract or "未提取到摘要")
            .replace(
                "{paper_text if paper_text.strip() else \"[PDF 提取不可用——请基于标题和摘要进行分析]\"}",
                paper_text,
            )
        )
