from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from paper_wiki.assets.builder import PaperAssetsBuilder
from paper_wiki.assets.models import PaperAssetsBundle
from paper_wiki.assets.reader import AssetsReader
from paper_wiki.core.config import Settings, get_settings
from paper_wiki.core.models import IngestResult, PriorWorksDoc, SciPatternDoc
from paper_wiki.ingestion.generators.pattern_generator import PatternGenerator
from paper_wiki.ingestion.generators.prior_works_generator import PriorWorksGenerator
from paper_wiki.ingestion.generators.summary_generator import SummaryGenerator
from paper_wiki.ingestion.latex_parser import LaTeXParser
from paper_wiki.ingestion.llm_client import LLMClient, build_llm_client
from paper_wiki.ingestion.prior_works_backfill import backfill_prior_works_from_arxiv

logger = logging.getLogger(__name__)

SEMANTIC_ARTIFACT_TARGETS = ("summary", "prior_works", "sci_pattern")
TARGET_ALIASES = {
    "summary": "summary",
    "prior_works": "prior_works",
    "prior-works": "prior_works",
    "prior": "prior_works",
    "sci_pattern": "sci_pattern",
    "sci-pattern": "sci_pattern",
    "pattern": "sci_pattern",
}


@dataclass(frozen=True)
class SemanticArtifactStep:
    """One independently runnable Layer 1 semantic artifact generation step."""

    target: str
    filename: str
    prompt_file: str | None
    generate: Callable[[PaperAssetsBundle, str | None], Any]
    serialize: Callable[[Any], str]


class IngestPipeline:
    """Layer0 到 Layer1 的编排入口：构建 assets，并按需生成独立语义产物。"""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
        parser: LaTeXParser | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or build_llm_client(self.settings)
        self.parser = parser or LaTeXParser(max_chars=self.settings.max_parse_chars)
        self.assets_builder = PaperAssetsBuilder(self.settings, self.parser)
        self.assets_reader = AssetsReader(self.settings)
        self.summary_generator = SummaryGenerator(
            self.llm,
            self.settings.resolved_prompts_dir(),
            max_context_chars=self.settings.max_parse_chars,
        )
        self.prior_works_generator = PriorWorksGenerator(
            self.llm,
            self.settings.resolved_prompts_dir(),
            max_context_chars=self.settings.max_parse_chars,
        )
        self.pattern_generator = PatternGenerator(
            self.llm,
            self.settings.resolved_prompts_dir(),
            max_context_chars=self.settings.max_parse_chars,
        )

    def run(
        self,
        slug: str,
        overwrite: bool = False,
        *,
        summary_prompt: str | None = None,
        prior_works_prompt: str | None = None,
        sci_pattern_prompt: str | None = None,
        only: Sequence[str] | None = None,
    ) -> IngestResult:
        """
        执行 ingest；不会更新 wiki、图谱、向量库等 Layer2/Layer3 资源。
        """
        logger.info("开始执行 Layer0/Layer1 ingest：slug=%s", slug)
        selected_targets = self._normalize_targets(only)

        paper_dir = self.settings.resolved_raw_dir() / slug
        artifact_dir = self.settings.resolved_artifacts_dir() / slug
        logger.debug("输入论文目录：%s", paper_dir)
        logger.debug("输出 artifact 目录：%s", artifact_dir)

        artifact_dir.mkdir(parents=True, exist_ok=True)

        summary_path = artifact_dir / "summary.md"
        prior_works_path = artifact_dir / "prior_works.json"
        sci_pattern_path = artifact_dir / "sci_pattern.json"
        manifest_path = artifact_dir / "manifest.json"
        steps = self._semantic_artifact_steps(
            summary_prompt=summary_prompt,
            prior_works_prompt=prior_works_prompt,
            sci_pattern_prompt=sci_pattern_prompt,
        )
        selected_steps = [step for step in steps if step.target in selected_targets]
        output_paths = {step.target: artifact_dir / step.filename for step in selected_steps}

        for path in output_paths.values():
            # 默认不覆盖已有人工修订结果，只有显式 --overwrite 才重写所选语义产物。
            if path.exists() and not overwrite:
                logger.error("目标产物已存在且未允许覆盖：%s", path)
                raise FileExistsError(f"{path} already exists. Use overwrite=True or --overwrite.")

        # 先生成/复用通用 assets，再通过 canonical bundle 供所选 generator 消费。
        total_steps = len(selected_steps) + 1
        logger.info("步骤 1/%d：构建 Layer1 通用 assets", total_steps)
        if manifest_path.exists() and not overwrite:
            logger.info("assets 已存在，复用 assets：%s", manifest_path)
        else:
            self.assets_builder.build(slug, overwrite=overwrite)
        bundle = self.assets_reader.load(slug)

        generated_paths: dict[str, Path] = {}
        generated_artifacts: dict[str, Any] = {}
        for index, step in enumerate(selected_steps, start=2):
            output_path = artifact_dir / step.filename
            logger.info("步骤 %d/%d：生成 %s", index, total_steps, step.filename)
            artifact = step.generate(bundle, step.prompt_file)
            if step.target == "prior_works" and isinstance(artifact, PriorWorksDoc):
                artifact = self._backfill_prior_works(artifact)
            output_path.write_text(step.serialize(artifact), encoding="utf-8")
            generated_paths[step.target] = output_path
            generated_artifacts[step.target] = artifact
            logger.info("已写入：%s", output_path)

        if "summary" in generated_paths:
            self._append_summary_semantic_context(
                summary_path,
                prior_works_path,
                sci_pattern_path,
                generated_artifacts=generated_artifacts,
            )
        logger.info("Layer1 语义产物生成完成：slug=%s, targets=%s", slug, ", ".join(selected_targets))

        # 返回路径和 canonical assets bundle，便于 CLI、测试或后续任务复用。
        return IngestResult(
            slug=slug,
            artifact_dir=artifact_dir,
            manifest_path=manifest_path,
            summary_path=summary_path,
            prior_works_path=prior_works_path,
            sci_pattern_path=sci_pattern_path,
            generated_paths=generated_paths,
            assets=bundle,
        )

    def _backfill_prior_works(self, artifact: PriorWorksDoc) -> PriorWorksDoc:
        """用 arXiv 检索结果静默回填 prior_works 的 title/authors/year/arxiv_id。

        属于生成流程的一环，用户无感知；即使回填过程整体出错，也只记录 warning 并
        返回原始 artifact，不应中断 ingest。
        """
        try:
            return backfill_prior_works_from_arxiv(artifact, self.settings)
        except Exception as exc:
            logger.warning("先前工作 arXiv 回填整体失败，保留原始抽取结果：%s", exc)
            return artifact

    def _semantic_artifact_steps(
        self,
        *,
        summary_prompt: str | None,
        prior_works_prompt: str | None,
        sci_pattern_prompt: str | None,
    ) -> list[SemanticArtifactStep]:
        return [
            SemanticArtifactStep(
                target="summary",
                filename="summary.md",
                prompt_file=summary_prompt,
                generate=self.summary_generator.generate,
                serialize=lambda artifact: str(artifact),
            ),
            SemanticArtifactStep(
                target="prior_works",
                filename="prior_works.json",
                prompt_file=prior_works_prompt,
                generate=self.prior_works_generator.generate,
                serialize=lambda artifact: artifact.model_dump_json(indent=2),
            ),
            SemanticArtifactStep(
                target="sci_pattern",
                filename="sci_pattern.json",
                prompt_file=sci_pattern_prompt,
                generate=self.pattern_generator.generate,
                serialize=lambda artifact: artifact.model_dump_json(indent=2),
            ),
        ]

    def _append_summary_semantic_context(
        self,
        summary_path: Path,
        prior_works_path: Path,
        sci_pattern_path: Path,
        *,
        generated_artifacts: dict[str, Any],
    ) -> None:
        """Append deterministic context from prior_works/sci_pattern to a freshly generated summary."""
        prior_works = self._prior_works_for_summary(prior_works_path, generated_artifacts)
        sci_pattern = self._sci_pattern_for_summary(sci_pattern_path, generated_artifacts)
        appendix = self._summary_semantic_context_markdown(prior_works, sci_pattern)
        if not appendix:
            return

        summary = summary_path.read_text(encoding="utf-8").rstrip()
        summary_path.write_text(f"{summary}\n\n{appendix}\n", encoding="utf-8")
        logger.info("已将 prior_works / sci_pattern 摘要追加到 summary.md：%s", summary_path)

    def _prior_works_for_summary(
        self,
        prior_works_path: Path,
        generated_artifacts: dict[str, Any],
    ) -> PriorWorksDoc | None:
        generated = generated_artifacts.get("prior_works")
        if isinstance(generated, PriorWorksDoc):
            return generated
        if not prior_works_path.exists():
            return None
        try:
            return PriorWorksDoc.model_validate_json(prior_works_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("无法读取 prior_works.json，跳过 summary 追加：%s", exc)
            return None

    def _sci_pattern_for_summary(
        self,
        sci_pattern_path: Path,
        generated_artifacts: dict[str, Any],
    ) -> SciPatternDoc | None:
        generated = generated_artifacts.get("sci_pattern")
        if isinstance(generated, SciPatternDoc):
            return generated
        if not sci_pattern_path.exists():
            return None
        try:
            return SciPatternDoc.model_validate_json(sci_pattern_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("无法读取 sci_pattern.json，跳过 summary 追加：%s", exc)
            return None

    def _summary_semantic_context_markdown(
        self,
        prior_works: PriorWorksDoc | None,
        sci_pattern: SciPatternDoc | None,
    ) -> str:
        blocks: list[str] = []
        if sci_pattern is not None:
            primary = self._pattern_label(sci_pattern.primary_pattern.value, sci_pattern.primary_pattern_name)
            secondary_labels = [
                self._pattern_label(pattern.value, name)
                for pattern, name in zip(sci_pattern.secondary_patterns, sci_pattern.secondary_pattern_names)
            ]
            pattern_lines = [
                "## 科学发现范式",
                "",
                f"- 主要范式：{primary}",
            ]
            if secondary_labels:
                pattern_lines.append(f"- 次要范式：{', '.join(secondary_labels)}")
            pattern_lines.append(f"- 分类理由：{sci_pattern.reasoning}")
            blocks.append("\n".join(pattern_lines))

        if prior_works is not None and prior_works.synthesis_narrative.strip():
            blocks.append(
                "\n".join(
                    [
                        "## 先前工作分析",
                        "",
                        prior_works.synthesis_narrative.strip(),
                    ]
                )
            )

        if not blocks:
            return ""
        return "\n\n".join(blocks)

    def _pattern_label(self, pattern_id: str, pattern_name: str) -> str:
        return f"{pattern_id} {pattern_name}".strip()

    def _normalize_targets(self, only: Sequence[str] | None) -> tuple[str, ...]:
        if not only:
            return SEMANTIC_ARTIFACT_TARGETS

        targets: list[str] = []
        for raw_target in only:
            normalized = TARGET_ALIASES.get(raw_target.strip().lower())
            if normalized is None:
                allowed = ", ".join(sorted(TARGET_ALIASES))
                raise ValueError(f"Unknown semantic artifact target: {raw_target}. Allowed values: {allowed}")
            if normalized not in targets:
                targets.append(normalized)
        return tuple(targets)
