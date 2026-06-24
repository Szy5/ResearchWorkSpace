from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich import print

from paper_wiki.core.config import get_settings
from paper_wiki.core.logging import configure_logging
from paper_wiki.ingestion.latex_parser import LaTeXParser
from paper_wiki.ingestion.pipeline import IngestPipeline

app = typer.Typer(help="Paper-Wiki Layer0/Layer1 tools.")
logger = logging.getLogger(__name__)


@app.command()
def parse(slug: str, verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志。")) -> None:
    """解析 raw/{slug} 的 LaTeX，并打印 Layer0 解析摘要。"""
    configure_logging(verbose)
    try:
        settings = get_settings()
        parsed = LaTeXParser(max_chars=settings.max_parse_chars).parse(settings.resolved_raw_dir() / slug)
        # parse 命令不调用 LLM，适合先检查主文件识别、章节命中和 token 规模。
        print(
            {
                "slug": parsed.slug,
                "title": parsed.title,
                "authors": parsed.authors,
                "entry_file": parsed.entry_file,
                "source_files": parsed.source_files,
                "estimated_tokens": parsed.estimated_tokens,
                "matched_sections": parsed.matched_sections,
            }
        )
    except Exception as exc:
        logger.exception("parse 执行失败：slug=%s", slug) if verbose else logger.error("parse 执行失败：%s", exc)
        raise typer.Exit(code=1) from exc


@app.command()
def ingest(
    slug: str,
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="允许覆盖已有 Layer1 三件套。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """
    生成 artifacts/{slug}/summary.md、prior_works.json 和 sci_pattern.json
    """
    configure_logging(verbose)
    try:
        result = IngestPipeline().run(slug, overwrite=overwrite)
        print(f"[green]Generated Layer1 artifacts for {slug}[/green]")
        print(f"- {Path(result.summary_path)}")
        print(f"- {Path(result.prior_works_path)}")
        print(f"- {Path(result.sci_pattern_path)}")
    except Exception as exc:
        logger.exception("ingest 执行失败：slug=%s", slug) if verbose else logger.error("ingest 执行失败：%s", exc)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
