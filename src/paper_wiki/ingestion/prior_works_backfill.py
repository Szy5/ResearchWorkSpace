from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime

from paper_wiki.core.config import Settings
from paper_wiki.core.models import PriorWorkEntry, PriorWorksDoc
from paper_wiki.discovery import search as discovery_search

logger = logging.getLogger(__name__)

_TITLE_MATCH_THRESHOLD = 0.82
_ARXIV_FOUNDING_YEAR = 1991


def backfill_prior_works_from_arxiv(doc: PriorWorksDoc, settings: Settings) -> PriorWorksDoc:
    """用 arXiv 标题检索结果回填 title/authors/year/arxiv_id。

    只在候选标题与 LLM 抽取的标题足够相似时才覆盖，检索失败或没有可信匹配时保留原始
    抽取结果——避免把一个无关论文的信息静默写成"已核实"的数据，留给人工审查兜底。
    """
    end_year = datetime.now().year + 1
    backfilled = [_backfill_entry(entry, settings, end_year) for entry in doc.prior_works]
    return doc.model_copy(update={"prior_works": backfilled})


def _backfill_entry(entry: PriorWorkEntry, settings: Settings, end_year: int) -> PriorWorkEntry:
    if entry.arxiv_id:
        return entry

    try:
        candidates = discovery_search.search(
            entry.title,
            _ARXIV_FOUNDING_YEAR,
            end_year,
            max_results=3,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001 - 回填是尽力而为，不应中断整个 ingest 流程
        logger.warning("先前工作 arXiv 回填检索失败，跳过：title=%s, err=%s", entry.title, exc)
        return entry

    match = next(
        (
            candidate
            for candidate in candidates
            if _title_similarity(entry.title, candidate.title) >= _TITLE_MATCH_THRESHOLD
        ),
        None,
    )
    if match is None:
        return entry

    logger.info("先前工作回填命中：%s -> %s (%s)", entry.title, match.title, match.arxiv_id)
    return entry.model_copy(
        update={
            "title": match.title or entry.title,
            "authors": ", ".join(match.authors) if match.authors else entry.authors,
            "year": match.year if match.year is not None else entry.year,
            "arxiv_id": match.arxiv_id or entry.arxiv_id,
        }
    )


def _title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
