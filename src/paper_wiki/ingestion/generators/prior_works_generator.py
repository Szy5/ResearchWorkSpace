from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from paper_wiki.core.models import ParsedPaper, PriorWorkEntry, PriorWorksDoc
from paper_wiki.ingestion.llm_client import LLMClient

logger = logging.getLogger(__name__)


class _PriorWorksLLMResponse(BaseModel):
    """模型原始 JSON 形状；后续会补充 target_slug 等本地字段。"""

    prior_works: list[PriorWorkEntry] = Field(default_factory=list)
    synthesis_narrative: str


class PriorWorksGenerator:
    """生成 prior_works.json，捕捉当前论文直接依赖的前作谱系。"""

    def __init__(self, llm: LLMClient, prompts_dir: Path) -> None:
        self.llm = llm
        self.prompts_dir = prompts_dir

    def generate(self, parsed: ParsedPaper) -> PriorWorksDoc:
        """调用 LLM 识别前作，并用 PriorWorksDoc 做 schema 校验。"""
        logger.info("开始生成 prior_works.json：slug=%s", parsed.slug)
        system = (self.prompts_dir / "prior_work_prompt.py").read_text(encoding="utf-8", errors="ignore")
        system += "\n\n请严格返回 JSON，不要返回 Markdown。"
        user = f"""
分析这篇研究论文，并识别直接促成其核心创新的 5-7 篇关键前作。

论文标题：
{parsed.title}

作者：
{", ".join(parsed.authors) if parsed.authors else "未知"}

摘要：
{parsed.abstract or "未提取到摘要"}

论文正文节选：
{parsed.raw_text}

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
        # complete_json 会自动处理 JSON fence、格式错误重试和 Pydantic 校验。
        response = self.llm.complete_json(system, user, _PriorWorksLLMResponse)
        doc = PriorWorksDoc(
            target_slug=parsed.slug,
            target_title=parsed.title,
            prior_works=response.prior_works,
            synthesis_narrative=response.synthesis_narrative,
        )
        logger.info("prior_works.json 生成完成：slug=%s, prior_works=%d", parsed.slug, len(doc.prior_works))
        return doc
