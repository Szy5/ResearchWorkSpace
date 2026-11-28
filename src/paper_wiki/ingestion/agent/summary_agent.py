"""Agent-mode summary generator that explores a paper folder and reuses SummaryGenerator cleanup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from paper_wiki.assets.models import PaperAssetsBundle
from paper_wiki.core.config import Settings, get_settings
from paper_wiki.ingestion.agent.loop import AgentUsage, PaperAgentLoop
from paper_wiki.ingestion.agent.sandbox import PaperSandbox
from paper_wiki.ingestion.generators.summary_generator import SummaryGenerator
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path

logger = logging.getLogger(__name__)

DEFAULT_AGENT_SUMMARY_PROMPT = "paper_summary_agent_v1.py"


class AgentSummaryOutput(BaseModel):
    """Cleaned summary markdown paired with Agent Loop observability metadata."""

    markdown: str
    trace_id: str | None = None
    steps: int
    usage: AgentUsage
    tool_calls_summary: list[str] = []


class AgentSummaryGenerator:
    """Generate summary.md by letting an Agent explore raw/{slug} + artifacts/{slug}/assets."""

    def __init__(
        self,
        summary_generator: SummaryGenerator,
        settings: Settings | None = None,
        *,
        agent_loop: PaperAgentLoop | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.summary_generator = summary_generator
        self.prompts_dir = summary_generator.prompts_dir
        self.agent_loop = agent_loop or PaperAgentLoop(self.settings)

    def generate_with_meta(
        self,
        bundle: PaperAssetsBundle,
        *,
        raw_dir: Path,
        prompt_file: str | None = None,
    ) -> AgentSummaryOutput:
        prompt_name = prompt_file or DEFAULT_AGENT_SUMMARY_PROMPT
        prompt_path = resolve_prompt_path(self.prompts_dir, prompt_name)
        prompt_vars = load_prompt_module(prompt_path)
        if (
            "paper_summary_agent_system_prompt" not in prompt_vars
            or "paper_summary_agent_user_prompt" not in prompt_vars
        ):
            logger.info(
                "Prompt %s 缺少 agent 模板变量，回退使用默认 %s",
                prompt_name,
                DEFAULT_AGENT_SUMMARY_PROMPT,
            )
            prompt_name = DEFAULT_AGENT_SUMMARY_PROMPT
            prompt_path = resolve_prompt_path(self.prompts_dir, prompt_name)
            prompt_vars = load_prompt_module(prompt_path)
        system = prompt_vars["paper_summary_agent_system_prompt"].strip()
        user_template = prompt_vars["paper_summary_agent_user_prompt"]

        sandbox = PaperSandbox(
            raw_dir=raw_dir,
            artifact_dir=bundle.artifact_dir,
            max_read_lines=self.settings.agent_max_read_lines,
            max_read_chars=self.settings.agent_max_read_chars,
            max_grep_matches=self.settings.agent_max_grep_matches,
        )
        paper_map = sandbox.build_initial_map(bundle)
        initial_user = user_template.replace("{PAPER_TITLE}", bundle.title).replace("{PAPER_MAP}", paper_map)

        raw_file_count, raw_tex_bytes = sandbox.raw_source_stats()
        size_tag = "long-paper" if raw_tex_bytes > 100_000 else "normal-paper"

        run_result = self.agent_loop.run(
            slug=bundle.slug,
            system_prompt=system,
            initial_user_prompt=initial_user,
            sandbox=sandbox,
            tags=["summary", "source:raw", size_tag],
            metadata={
                "primary_source": "raw",
                "prompt_file": Path(prompt_name).name,
                "raw_file_count": raw_file_count,
                "raw_tex_bytes": raw_tex_bytes,
                "section_count": len(bundle.sections.sections),
                "figure_count": len(bundle.figures.figures),
            },
        )

        # Reuse existing deterministic cleaning and figure post-processing so output stays 100% compatible.
        content = self.summary_generator._rewrite_figure_paths(run_result.content, bundle)
        summary = self.summary_generator._clean_summary_content(content)
        summary = self.summary_generator._deduplicate_figures(summary, bundle)
        summary = self.summary_generator._supplement_figures(summary, bundle)
        summary = self.summary_generator._deduplicate_figures(summary, bundle)
        summary = self.summary_generator._number_figure_captions(summary)

        logger.info(
            "Agent summary.md 生成完成：slug=%s, chars=%d, steps=%d, tools=%d, trace_id=%s",
            bundle.slug,
            len(summary),
            run_result.steps,
            run_result.usage.tool_calls,
            run_result.trace_id,
        )
        return AgentSummaryOutput(
            markdown=summary,
            trace_id=run_result.trace_id,
            steps=run_result.steps,
            usage=run_result.usage,
            tool_calls_summary=[f"{rec.step}:{rec.name}" for rec in run_result.tool_history],
        )

    def generate(
        self,
        bundle: PaperAssetsBundle,
        *,
        raw_dir: Path,
        prompt_file: str | None = None,
    ) -> str:
        return self.generate_with_meta(bundle, raw_dir=raw_dir, prompt_file=prompt_file).markdown

    def stats_dict(self, output: AgentSummaryOutput) -> dict[str, Any]:
        return {
            "mode": "agent",
            "steps": output.steps,
            "trace_id": output.trace_id,
            "prompt_tokens": output.usage.prompt_tokens,
            "cached_tokens": output.usage.cached_tokens,
            "cache_write_tokens": output.usage.cache_write_tokens,
            "completion_tokens": output.usage.completion_tokens,
            "total_tokens": output.usage.total_tokens,
            "llm_calls": output.usage.llm_calls,
            "tool_calls": output.usage.tool_calls,
        }
