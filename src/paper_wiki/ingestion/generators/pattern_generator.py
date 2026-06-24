from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from paper_wiki.core.enums import ConfidenceLevel, PatternID
from paper_wiki.core.models import ParsedPaper, SciPatternDoc
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path

logger = logging.getLogger(__name__)


class _PatternClassification(BaseModel):
    paper_index: int | None = None
    primary_pattern: PatternID
    secondary_patterns: list[PatternID] = Field(default_factory=list)
    confidence: ConfidenceLevel
    reasoning: str


class _PatternLLMResponse(BaseModel):
    classifications: list[_PatternClassification] = Field(default_factory=list)


class PatternGenerator:
    """生成 sci_pattern.json，把论文创新归入 Sci-Reasoning 范式体系。"""

    def __init__(self, llm: LLMClient, prompts_dir: Path) -> None:
        self.llm = llm
        self.prompts_dir = prompts_dir

    def generate(self, parsed: ParsedPaper, prompt_file: str | None = None) -> SciPatternDoc:
        """加载 taxonomy 与 prompt，解析 classifications 并写入单篇 sci_pattern.json。"""
        logger.info("开始生成 sci_pattern.json：slug=%s", parsed.slug)
        taxonomy = json.loads((self.prompts_dir / "pattern_taxonomy.json").read_text(encoding="utf-8"))
        taxonomy_text = json.dumps(taxonomy, ensure_ascii=False, indent=2)
        papers_text = (
            f"Title: {parsed.title}\n"
            f"Abstract: {parsed.abstract or 'N/A'}\n\n"
            f"Content:\n{parsed.raw_text}"
        )

        prompt_path = resolve_prompt_path(self.prompts_dir, prompt_file or "sci_pattern_classify_prompt.py")
        logger.debug("使用 sci_pattern prompt：%s", prompt_path)
        prompt_vars = load_prompt_module(prompt_path)
        system = prompt_vars["sci_pattern_classify_system_prompt"].strip()
        user = (
            prompt_vars["sci_pattern_classify_user_prompt"]
            .replace("{taxonomy_ref}", taxonomy_text)
            .replace("{papers_text}", papers_text)
        )

        response = self.llm.complete_json(system, user, _PatternLLMResponse)
        if not response.classifications:
            raise ValueError("LLM returned empty classifications list")
        classification = response.classifications[0]

        pattern_names = self._pattern_name_map(taxonomy)
        doc = SciPatternDoc(
            target_slug=parsed.slug,
            target_title=parsed.title,
            primary_pattern=classification.primary_pattern,
            primary_pattern_name=pattern_names.get(classification.primary_pattern.value, ""),
            secondary_patterns=classification.secondary_patterns,
            secondary_pattern_names=[
                pattern_names.get(pattern.value, "") for pattern in classification.secondary_patterns
            ],
            confidence=classification.confidence,
            reasoning=classification.reasoning,
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
