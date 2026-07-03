from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich import print

from paper_wiki.core.config import get_settings
from paper_wiki.core.logging import configure_logging
from paper_wiki.graph.neo4j_store import Neo4jGraphStore, load_graph_event
from paper_wiki.graph.planner import GraphPlanner
from paper_wiki.graph.state_store import GraphStateStore
from paper_wiki.ingestion.latex_parser import LaTeXParser
from paper_wiki.ingestion.pipeline import IngestPipeline

app = typer.Typer(help="Paper-Wiki Layer0/Layer1 tools.")
graph_app = typer.Typer(help="Paper-Wiki Layer2 scientific discovery graph tools.")
logger = logging.getLogger(__name__)

LAYER1_ARTIFACT_FILES = ("summary.md", "prior_works.json", "sci_pattern.json")


def _is_raw_paper_dir(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith(".") and any(path.rglob("*.tex"))


def _has_complete_layer1_artifacts(artifacts_dir: Path, slug: str) -> bool:
    artifact_dir = artifacts_dir / slug
    return all((artifact_dir / filename).exists() for filename in LAYER1_ARTIFACT_FILES)


def discover_pending_slugs(raw_dir: Path, artifacts_dir: Path, *, overwrite: bool = False) -> list[str]:
    """发现 raw/ 下需要生成 Layer1 三件套的论文目录。"""
    if not raw_dir.exists():
        raise FileNotFoundError(f"raw directory does not exist: {raw_dir}")

    slugs: list[str] = []
    for paper_dir in sorted(raw_dir.iterdir(), key=lambda path: path.name):
        if not _is_raw_paper_dir(paper_dir):
            continue
        if overwrite or not _has_complete_layer1_artifacts(artifacts_dir, paper_dir.name):
            slugs.append(paper_dir.name)
    return slugs


def _run_ingest_for_slugs(
    slugs: list[str],
    *,
    overwrite: bool,
    verbose: bool,
    summary_prompt: str | None,
    prior_works_prompt: str | None,
    sci_pattern_prompt: str | None,
) -> None:
    if not slugs:
        print("[yellow]No pending raw papers found.[/yellow]")
        return

    try:
        pipeline = IngestPipeline()
    except Exception as exc:
        logger.exception("ingest 初始化失败") if verbose else logger.error("ingest 初始化失败：%s", exc)
        raise typer.Exit(code=1) from exc

    failures: list[str] = []

    for slug in slugs:
        try:
            result = pipeline.run(
                slug,
                overwrite=overwrite,
                summary_prompt=summary_prompt,
                prior_works_prompt=prior_works_prompt,
                sci_pattern_prompt=sci_pattern_prompt,
            )
            print(f"[green]Generated Layer1 artifacts for {slug}[/green]")
            print(f"- {Path(result.summary_path)}")
            print(f"- {Path(result.prior_works_path)}")
            print(f"- {Path(result.sci_pattern_path)}")
        except Exception as exc:
            failures.append(slug)
            if verbose:
                logger.exception("ingest 执行失败：slug=%s", slug)
            else:
                logger.error("ingest 执行失败：slug=%s, error=%s", slug, exc)

    if failures:
        print(f"[red]Failed to generate Layer1 artifacts for {len(failures)} slug(s): {', '.join(failures)}[/red]")
        raise typer.Exit(code=1)


def _build_graph_planner() -> GraphPlanner:
    settings = get_settings()
    return GraphPlanner(
        settings.resolved_artifacts_dir(),
        settings.resolved_graph_state_dir(),
        settings.resolved_graph_updates_dir(),
    )


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
    slugs: list[str] = typer.Argument(..., help="一个或多个 raw/{slug} 目录名。"),
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="允许覆盖已有 Layer1 三件套。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
    summary_prompt: str | None = typer.Option(
        "paper_summary_v2.py",
        "--summary-prompt",
        help="摘要 prompt 文件，默认 paper_summary.py；可传相对 prompts/ 的路径或绝对路径。",
    ),
    prior_works_prompt: str | None = typer.Option(
        "prior_work_prompt.py",
        "--prior-works-prompt",
        help="前作谱系 prompt 文件，默认 prior_work_prompt.py。",
    ),
    sci_pattern_prompt: str | None = typer.Option(
        "sci_pattern_classify_prompt.py",
        "--sci-pattern-prompt",
        help="科学范式 prompt 文件，默认 sci_pattern_classify_prompt.py。",
    ),
) -> None:
    """
    生成一个或多个 artifacts/{slug}/ 下的 summary.md、prior_works.json 和 sci_pattern.json
    """
    configure_logging(verbose)
    _run_ingest_for_slugs(
        slugs,
        overwrite=overwrite,
        verbose=verbose,
        summary_prompt=summary_prompt,
        prior_works_prompt=prior_works_prompt,
        sci_pattern_prompt=sci_pattern_prompt,
    )


@app.command("ingest-all")
def ingest_all(
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="重跑 raw/ 下所有论文；默认只处理未生成完整三件套的论文。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
    summary_prompt: str | None = typer.Option(
        "paper_summary_v2.py",
        "--summary-prompt",
        help="摘要 prompt 文件，默认 paper_summary.py；可传相对 prompts/ 的路径或绝对路径。",
    ),
    prior_works_prompt: str | None = typer.Option(
        "prior_work_prompt.py",
        "--prior-works-prompt",
        help="前作谱系 prompt 文件，默认 prior_work_prompt.py。",
    ),
    sci_pattern_prompt: str | None = typer.Option(
        "sci_pattern_classify_prompt.py",
        "--sci-pattern-prompt",
        help="科学范式 prompt 文件，默认 sci_pattern_classify_prompt.py。",
    ),
) -> None:
    """
    扫描 raw/ 下所有论文目录，并为未生成完整三件套的论文生成 Layer1 artifacts。
    """
    configure_logging(verbose)
    try:
        settings = get_settings()
        slugs = discover_pending_slugs(
            settings.resolved_raw_dir(),
            settings.resolved_artifacts_dir(),
            overwrite=overwrite,
        )
    except Exception as exc:
        logger.exception("ingest-all 扫描失败") if verbose else logger.error("ingest-all 扫描失败：%s", exc)
        raise typer.Exit(code=1) from exc

    print(f"[cyan]Found {len(slugs)} raw paper(s) to ingest.[/cyan]")
    _run_ingest_for_slugs(
        slugs,
        overwrite=overwrite,
        verbose=verbose,
        summary_prompt=summary_prompt,
        prior_works_prompt=prior_works_prompt,
        sci_pattern_prompt=sci_pattern_prompt,
    )


@graph_app.command("plan")
def graph_plan(
    slugs: list[str] = typer.Argument(..., help="一个或多个 reviewed artifacts/{slug} 目录名。"),
    include_unreviewed: bool = typer.Option(False, "--include-unreviewed", help="允许为未 review 的 artifact 生成图谱事件。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """从 reviewed artifacts 生成 Layer2 图谱快照和增量 JSONL 事件。"""
    configure_logging(verbose)
    planner = _build_graph_planner()
    failures: list[str] = []

    for slug in slugs:
        try:
            result = planner.plan_slug(slug, include_unreviewed=include_unreviewed)
            print(f"[green]Planned graph updates for {slug}[/green]")
            print(f"- events: {len(result.events)}")
            print(f"- papers: {len(result.paper_keys)}")
            print(f"- relations: {len(result.relation_keys)}")
        except Exception as exc:
            failures.append(slug)
            if verbose:
                logger.exception("graph plan 执行失败：slug=%s", slug)
            else:
                logger.error("graph plan 执行失败：slug=%s, error=%s", slug, exc)

    if failures:
        print(f"[red]Failed to plan graph updates for {len(failures)} slug(s): {', '.join(failures)}[/red]")
        raise typer.Exit(code=1)


@graph_app.command("apply")
def graph_apply(
    since_checkpoint: bool = typer.Option(True, "--since-checkpoint/--from-start", help="默认只应用未处理的 JSONL 事件。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """把图谱 JSONL 增量事件幂等写入 Neo4j。"""
    configure_logging(verbose)
    settings = get_settings()
    store = GraphStateStore(settings.resolved_graph_state_dir(), settings.resolved_graph_updates_dir())
    lines = store.load_events()
    checkpoint = store.load_checkpoint()
    start_index = checkpoint.applied_line_count if since_checkpoint else 0
    pending_lines = lines[start_index:]
    if not pending_lines:
        print("[yellow]No pending graph events to apply.[/yellow]")
        return

    graph_store = Neo4jGraphStore(settings)
    try:
        graph_store.ensure_schema()
        for line in pending_lines:
            graph_store.apply_event(load_graph_event(line))
    finally:
        graph_store.close()

    checkpoint.applied_line_count = len(lines) if since_checkpoint else len(lines)
    store.save_checkpoint(checkpoint)
    print(f"[green]Applied {len(pending_lines)} graph event(s) to Neo4j[/green]")


app.add_typer(graph_app, name="graph")


if __name__ == "__main__":
    app()
