from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from paper_wiki.core.enums import ConfidenceLevel, PatternID
from paper_wiki.core.models import ParsedPaper, SciPatternDoc
from paper_wiki.ingestion.llm_client import LLMClient

logger = logging.getLogger(__name__)


class _PatternLLMResponse(BaseModel):
    """模型返回的范式分类最小结构。"""

    primary_pattern: PatternID
    secondary_patterns: list[PatternID] = Field(default_factory=list)
    confidence: ConfidenceLevel
    reasoning: str


class PatternGenerator:
    """生成 sci_pattern.json，把论文创新归入 Sci-Reasoning 范式体系。"""

    def __init__(self, llm: LLMClient, prompts_dir: Path) -> None:
        self.llm = llm
        self.prompts_dir = prompts_dir

    def generate(self, parsed: ParsedPaper) -> SciPatternDoc:
        """加载本地 taxonomy，让模型只输出 ID，再在本地补齐范式名称。"""
        logger.info("开始生成 sci_pattern.json：slug=%s", parsed.slug)
        taxonomy = json.loads((self.prompts_dir / "pattern_taxonomy.json").read_text(encoding="utf-8"))
        taxonomy_text = json.dumps(taxonomy, ensure_ascii=False, indent=2)
        system = "You are an expert at classifying scientific innovation patterns. Return JSON only."
        user = f"""
TAXONOMY:
{taxonomy_text}

PAPER:
Title: {parsed.title}
Abstract: {parsed.abstract or "N/A"}

Content:
{parsed.raw_text}

Classify this paper. Return exactly:
{{
  "primary_pattern": "P01",
  "secondary_patterns": ["P03"],
  "confidence": "high|medium|low",
  "reasoning": "brief but specific classification reason"
}}
""".strip()
        response = self.llm.complete_json(system, user, _PatternLLMResponse)
        pattern_names = self._pattern_name_map(taxonomy)
        doc = SciPatternDoc(
            target_slug=parsed.slug,
            target_title=parsed.title,
            primary_pattern=response.primary_pattern,
            primary_pattern_name=pattern_names.get(response.primary_pattern.value, ""),
            secondary_patterns=response.secondary_patterns,
            secondary_pattern_names=[pattern_names.get(pattern.value, "") for pattern in response.secondary_patterns],
            confidence=response.confidence,
            reasoning=response.reasoning,
        )
        logger.info(
            "sci_pattern.json 生成完成：slug=%s, primary_pattern=%s, confidence=%s",
            parsed.slug,
            doc.primary_pattern.value,
            doc.confidence.value,
        )
        return doc

    def _pattern_name_map(self, taxonomy: dict) -> dict[str, str]:
        """把 P01/P02 这类 ID 映射成人类可读名称。"""
        return {entry["id"]: entry["name"] for entry in taxonomy.get("taxonomy", [])}
