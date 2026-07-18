from __future__ import annotations

from paper_wiki.core.config import Settings, get_settings
from paper_wiki.discovery.models import FetchResult, SearchCandidate, ZoteroCorpusEntry
from paper_wiki.discovery.sources import arxiv_source, zotero_source


def search(
    query: str,
    start_year: int,
    end_year: int,
    max_results: int | None = None,
    *,
    settings: Settings | None = None,
) -> list[SearchCandidate]:
    """
    根据关键词检索 arxiv 论文。

    Args:
        query: 关键词。
        start_year: 起始年份。
        end_year: 结束年份。
        max_results: 最大返回条数，默认读取 SEARCH_MAX_RESULTS。
        settings: 配置对象，可选。
    """
    settings = settings or get_settings()
    return arxiv_source.search_by_query(
        query,
        start_year,
        end_year,
        max_results or settings.search_max_results,
        settings=settings,
    )


def fetch(
    arxiv_id: str,
    *,
    and_ingest: bool = False,
    overwrite: bool = False,
    settings: Settings | None = None,
) -> FetchResult:
    """
    下载 arxiv 论文源码并提取主文件。

    Args:
        arxiv_id: arXiv ID，例如 2401.12345。
        and_ingest: 是否立即运行 Layer1 ingest，默认 False。
        overwrite: 是否覆盖已有 raw/{slug}/ 目录，默认 False。
        settings: 配置对象，可选。
    """
    settings = settings or get_settings()
    result = arxiv_source.fetch(arxiv_id, settings=settings, overwrite=overwrite)
    if and_ingest:
        from paper_wiki.ingestion.pipeline import IngestPipeline

        IngestPipeline(settings=settings).run(result.slug, overwrite=overwrite)
    return result


def daily_candidates(
    category_query: str,
    max_results: int = 200,
    *,
    settings: Settings | None = None,
) -> list[SearchCandidate]:
    """
    根据分类查询 arxiv 每日候选论文。

    Args:
        category_query: 分类查询。
        max_results: 最大返回条数，默认 200。
        settings: 配置对象，可选。

    """
    settings = settings or get_settings()
    return arxiv_source.daily_candidates(category_query, max_results=max_results, settings=settings)


def zotero_corpus(*, settings: Settings | None = None) -> list[ZoteroCorpusEntry]:
    settings = settings or get_settings()
    return zotero_source.zotero_corpus(
        settings.zotero_id or "",
        settings.zotero_key or "",
        library_type=settings.zotero_library_type,
        ignore_pattern=settings.zotero_ignore,
    )
