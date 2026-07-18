from __future__ import annotations

import logging

from paper_wiki.core.config import Settings
from paper_wiki.discovery.models import RecommendationSnapshot
from paper_wiki.discovery.recommend import write_snapshot
from paper_wiki.ingestion.llm_client import build_llm_client
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_FILE = "candidate_summary_v1.py"


def enrich_with_display_summary(
    snapshot: RecommendationSnapshot,
    settings: Settings,
    *,
    prompt_file: str = DEFAULT_PROMPT_FILE,
) -> None:
    """Generate a short LLM summary for each candidate already in the snapshot.

    Only operates on the already-ranked, already-capped ``snapshot.candidates``
    (e.g. 15 entries), never the full candidate pool, so cost stays bounded to
    what TodayFeed actually shows. A single candidate's failure is logged and
    skipped; the card falls back to the raw abstract on the frontend.
    """
    if not snapshot.candidates:
        return

    prompt_path = resolve_prompt_path(settings.resolved_prompts_dir(), prompt_file)
    prompt_vars = load_prompt_module(prompt_path)
    system = prompt_vars["candidate_summary_system_prompt"].strip()
    user_template = prompt_vars["candidate_summary_user_prompt"]

    llm = build_llm_client(settings)
    total = len(snapshot.candidates)
    for index, candidate in enumerate(snapshot.candidates, start=1):
        logger.info("正在为候选生成摘要 (%d/%d)", index, total)
        user = user_template.replace("{PAPER_TITLE}", candidate.title).replace(
            "{PAPER_ABSTRACT}", candidate.abstract or "（无摘要）"
        )
        try:
            candidate.display_summary = llm.complete(system, user).strip()
        except Exception as exc:  # noqa: BLE001 - one bad candidate must not abort the batch
            logger.warning("候选摘要生成失败，回退到原始摘要：title=%s, error=%s", candidate.title, exc)

    write_snapshot(snapshot, settings)
