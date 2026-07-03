from __future__ import annotations

import logging
from pathlib import Path

from paper_wiki.core.config import Settings, get_settings
from paper_wiki.core.models import IngestResult
from paper_wiki.ingestion.generators.pattern_generator import PatternGenerator
from paper_wiki.ingestion.generators.prior_works_generator import PriorWorksGenerator
from paper_wiki.ingestion.generators.summary_generator import SummaryGenerator
from paper_wiki.ingestion.latex_parser import LaTeXParser
from paper_wiki.ingestion.llm_client import LLMClient, build_llm_client
from paper_wiki.ingestion.summary_figure_converter import convert_summary_pdf_figures

logger = logging.getLogger(__name__)


class IngestPipeline:
    """Layer0 到 Layer1 的编排入口：只生成单篇论文三件套。"""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
        parser: LaTeXParser | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or build_llm_client(self.settings)
        self.parser = parser or LaTeXParser(max_chars=self.settings.max_parse_chars)
        self.summary_generator = SummaryGenerator(self.llm, self.settings.resolved_prompts_dir())
        self.prior_works_generator = PriorWorksGenerator(self.llm, self.settings.resolved_prompts_dir())
        self.pattern_generator = PatternGenerator(self.llm, self.settings.resolved_prompts_dir())

    def run(
        self,
        slug: str,
        overwrite: bool = False,
        *,
        summary_prompt: str | None = None,
        prior_works_prompt: str | None = None,
        sci_pattern_prompt: str | None = None,
    ) -> IngestResult:
        """
        执行 ingest；不会更新 wiki、图谱、向量库等 Layer2/Layer3 资源。
        """
        logger.info("开始执行 Layer0/Layer1 ingest：slug=%s", slug)

        paper_dir = self.settings.resolved_raw_dir() / slug
        artifact_dir = self.settings.resolved_artifacts_dir() / slug
        logger.debug("输入论文目录：%s", paper_dir)
        logger.debug("输出 artifact 目录：%s", artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        summary_path = artifact_dir / "summary.md"
        prior_works_path = artifact_dir / "prior_works.json"
        sci_pattern_path = artifact_dir / "sci_pattern.json"
        for path in [summary_path, prior_works_path, sci_pattern_path]:
            # 默认不覆盖已有人工修订结果，只有显式 --overwrite 才重写三件套。
            if path.exists() and not overwrite:
                logger.error("目标产物已存在且未允许覆盖：%s", path)
                raise FileExistsError(f"{path} already exists. Use overwrite=True or --overwrite.")

        # 先把原始 LaTeX 压成 ParsedPaper，再分别交给三个生成器。
        logger.info("步骤 1/4：解析 Layer0 LaTeX 原始资料")
        parsed = self.parser.parse(paper_dir)

        logger.info("步骤 2/4：生成 summary.md")
        summary = self.summary_generator.generate(parsed, prompt_file=summary_prompt)
        summary_path.write_text(summary, encoding="utf-8")
        logger.info("已写入：%s", summary_path)

        figure_result = convert_summary_pdf_figures(
            summary_path,
            slug=slug,
            raw_dir=self.settings.resolved_raw_dir(),
            artifact_dir=artifact_dir,
        )
        if figure_result.converted:
            logger.info(
                "summary 图片已转换：slug=%s, converted=%d, skipped=%d",
                slug,
                len(figure_result.converted),
                len(figure_result.skipped),
            )

        logger.info("步骤 3/4：生成 prior_works.json")
        prior_works = self.prior_works_generator.generate(parsed, prompt_file=prior_works_prompt)
        prior_works_path.write_text(prior_works.model_dump_json(indent=2), encoding="utf-8")
        logger.info("已写入：%s", prior_works_path)

        logger.info("步骤 4/4：生成 sci_pattern.json")
        sci_pattern = self.pattern_generator.generate(parsed, prompt_file=sci_pattern_prompt)
        sci_pattern_path.write_text(sci_pattern.model_dump_json(indent=2), encoding="utf-8")
        logger.info("已写入：%s", sci_pattern_path)
        logger.info("Layer1 三件套生成完成：slug=%s", slug)

        # 返回路径和解析摘要，便于 CLI、测试或后续任务复用。
        return IngestResult(
            slug=slug,
            artifact_dir=artifact_dir,
            summary_path=summary_path,
            prior_works_path=prior_works_path,
            sci_pattern_path=sci_pattern_path,
            parsed=parsed,
        )
