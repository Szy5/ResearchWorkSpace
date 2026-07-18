from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich import print

from paper_wiki.assets.builder import PaperAssetsBuilder
from paper_wiki.assets.models import AssetsManifest
from paper_wiki.core.config import get_settings
from paper_wiki.core.logging import configure_logging
from paper_wiki.discovery import recommend as recommend_service
from paper_wiki.discovery import search as discovery_search
from paper_wiki.discovery.exceptions import DiscoveryError, RecommendError
from paper_wiki.graph.neo4j_store import Neo4jGraphStore, load_graph_event
from paper_wiki.graph.planner import GraphPlanner
from paper_wiki.graph.state_store import GraphStateStore
from paper_wiki.ingestion.latex_parser import LaTeXParser
from paper_wiki.ingestion.pipeline import IngestPipeline, TARGET_ALIASES
from paper_wiki.publishing.cursor_render import render_blog_html
from paper_wiki.publishing.exceptions import PublishingError
from paper_wiki.publishing.models import WeChatDraftOptions
from paper_wiki.publishing.wechat_publisher import publish_artifact_html_to_wechat
from paper_wiki.web.services.paper_repository import PaperRepository

app = typer.Typer(help="Paper-Wiki Layer0/Layer1 tools.")
graph_app = typer.Typer(help="Paper-Wiki Layer2 scientific discovery graph tools.")
publish_app = typer.Typer(help="Publish generated artifacts to external channels.")
recommend_app = typer.Typer(help="Paper-Wiki discovery recommendation tools.")
logger = logging.getLogger(__name__)

SEMANTIC_ARTIFACT_FILES = {
    "summary": "summary.md",
    "prior_works": "prior_works.json",
    "sci_pattern": "sci_pattern.json",
}
LAYER1_ARTIFACT_FILES = ("manifest.json", *SEMANTIC_ARTIFACT_FILES.values())
ASSET_CONTRACT_FILES = (
    "manifest.json",
    "assets/paper.md",
    "assets/sections.json",
    "assets/figures/manifest.json",
    "assets/references.json",
)


def _is_raw_paper_dir(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith(".") and any(path.rglob("*.tex"))


def _normalize_only_targets(only: list[str] | None) -> tuple[str, ...] | None:
    if not only:
        return None
    targets: list[str] = []
    for raw_target in only:
        target = TARGET_ALIASES.get(raw_target.strip().lower())
        if target is None:
            allowed = ", ".join(sorted(TARGET_ALIASES))
            raise ValueError(f"Unknown semantic artifact target: {raw_target}. Allowed values: {allowed}")
        if target not in targets:
            targets.append(target)
    return tuple(targets)


def _has_complete_layer1_artifacts(artifacts_dir: Path, slug: str, *, only: list[str] | None = None) -> bool:
    artifact_dir = artifacts_dir / slug
    targets = _normalize_only_targets(only)
    selected_artifact_files = (
        [SEMANTIC_ARTIFACT_FILES[target] for target in targets]
        if targets
        else list(SEMANTIC_ARTIFACT_FILES.values())
    )
    required_files = ["manifest.json", *selected_artifact_files]
    return all((artifact_dir / filename).exists() for filename in required_files)


def _has_complete_assets(artifacts_dir: Path, slug: str) -> bool:
    artifact_dir = artifacts_dir / slug
    return all((artifact_dir / filename).exists() for filename in ASSET_CONTRACT_FILES)


def discover_pending_slugs(
    raw_dir: Path,
    artifacts_dir: Path,
    *,
    overwrite: bool = False,
    only: list[str] | None = None,
) -> list[str]:
    """发现 raw/ 下需要生成 Layer1 语义产物的论文目录。"""
    if not raw_dir.exists():
        raise FileNotFoundError(f"raw directory does not exist: {raw_dir}")

    slugs: list[str] = []
    for paper_dir in sorted(raw_dir.iterdir(), key=lambda path: path.name):
        if not _is_raw_paper_dir(paper_dir):
            continue
        if overwrite or not _has_complete_layer1_artifacts(artifacts_dir, paper_dir.name, only=only):
            slugs.append(paper_dir.name)
    return slugs


def discover_reviewed_slugs(artifacts_dir: Path) -> list[str]:
    """扫描 artifacts/ 下 meta_reviewed 且 prior_works_reviewed 均为真的论文目录。"""
    if not artifacts_dir.exists():
        raise FileNotFoundError(f"artifacts directory does not exist: {artifacts_dir}")

    slugs: list[str] = []
    for artifact_dir in sorted(artifacts_dir.iterdir(), key=lambda path: path.name):
        if not artifact_dir.is_dir() or artifact_dir.name.startswith("."):
            continue
        manifest_path = artifact_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = AssetsManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if manifest.paper.meta_reviewed and manifest.paper.prior_works_reviewed:
            slugs.append(artifact_dir.name)
    return slugs


def _run_ingest_for_slugs(
    slugs: list[str],
    *,
    overwrite: bool,
    verbose: bool,
    summary_prompt: str | None,
    prior_works_prompt: str | None,
    sci_pattern_prompt: str | None,
    only: list[str] | None,
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
                only=only,
            )
            print(f"[green]Generated Layer1 semantic artifacts for {slug}[/green]")
            if manifest_path := getattr(result, "manifest_path", None):
                print(f"- {Path(manifest_path)}")
            generated_paths = getattr(result, "generated_paths", None) or {
                "summary": result.summary_path,
                "prior_works": result.prior_works_path,
                "sci_pattern": result.sci_pattern_path,
            }
            for path in generated_paths.values():
                print(f"- {Path(path)}")
        except Exception as exc:
            failures.append(slug)
            if verbose:
                logger.exception("ingest 执行失败：slug=%s", slug)
            else:
                logger.error("ingest 执行失败：slug=%s, error=%s", slug, exc)

    if failures:
        print(
            f"[red]Failed to generate Layer1 semantic artifacts for {len(failures)} slug(s): "
            f"{', '.join(failures)}[/red]"
        )
        raise typer.Exit(code=1)


def _run_assets_for_slugs(slugs: list[str], *, overwrite: bool, verbose: bool) -> None:
    if not slugs:
        print("[yellow]No raw papers provided.[/yellow]")
        return

    try:
        builder = PaperAssetsBuilder()
    except Exception as exc:
        logger.exception("assets 初始化失败") if verbose else logger.error("assets 初始化失败：%s", exc)
        raise typer.Exit(code=1) from exc

    failures: list[str] = []
    for slug in slugs:
        try:
            result = builder.build(slug, overwrite=overwrite)
            print(f"[green]Generated assets for {slug}[/green]")
            print(f"- {Path(result.manifest_path)}")
            print(f"- {Path(result.paper_path)}")
            print(f"- {Path(result.sections_path)}")
            print(f"- {Path(result.figures_manifest_path)}")
            print(f"- {Path(result.references_path)}")
        except Exception as exc:
            failures.append(slug)
            if verbose:
                logger.exception("assets 构建失败：slug=%s", slug)
            else:
                logger.error("assets 构建失败：slug=%s, error=%s", slug, exc)

    if failures:
        print(f"[red]Failed to generate assets for {len(failures)} slug(s): {', '.join(failures)}[/red]")
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


@app.command("assets")
def build_assets(
    slugs: list[str] = typer.Argument(..., help="一个或多个 raw/{slug} 目录名。"),
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="允许覆盖已有 assets。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """只构建 artifacts/{slug}/ 下的通用 assets，不调用 LLM，不生成语义产物。"""
    configure_logging(verbose)
    _run_assets_for_slugs(slugs, overwrite=overwrite, verbose=verbose)


@app.command()
def ingest(
    slugs: list[str] = typer.Argument(..., help="一个或多个 raw/{slug} 目录名。"),
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="允许覆盖所选 Layer1 语义产物。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
    only: list[str] | None = typer.Option(
        None,
        "--only",
        help="只生成指定语义产物，可重复传入：summary、prior_works、sci_pattern；也接受 prior-works、pattern。",
    ),
    summary_prompt: str | None = typer.Option(
        "paper_summary_v3.py",
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
    生成一个或多个 artifacts/{slug}/ 下的独立 Layer1 语义产物。
    """
    configure_logging(verbose)
    try:
        _normalize_only_targets(only)
    except ValueError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc
    _run_ingest_for_slugs(
        slugs,
        overwrite=overwrite,
        verbose=verbose,
        summary_prompt=summary_prompt,
        prior_works_prompt=prior_works_prompt,
        sci_pattern_prompt=sci_pattern_prompt,
        only=only,
    )


@app.command("ingest-all")
def ingest_all(
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="重跑 raw/ 下所有论文；默认只处理缺少语义产物的论文。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
    only: list[str] | None = typer.Option(
        None,
        "--only",
        help="只生成指定语义产物，可重复传入：summary、prior_works、sci_pattern；也接受 prior-works、pattern。",
    ),
    summary_prompt: str | None = typer.Option(
        "paper_summary_v3.py",
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
    扫描 raw/ 下所有论文目录，并为缺少所选语义产物的论文生成 Layer1 产物。
    """
    configure_logging(verbose)
    try:
        _normalize_only_targets(only)
        settings = get_settings()
        slugs = discover_pending_slugs(
            settings.resolved_raw_dir(),
            settings.resolved_artifacts_dir(),
            overwrite=overwrite,
            only=only,
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
        only=only,
    )


@app.command("search")
def search_papers(
    query: str = typer.Argument(..., help="arXiv 关键词检索查询。"),
    start_year: int = typer.Option(2020, "--start-year", help="起始年份。"),
    end_year: int = typer.Option(2026, "--end-year", help="结束年份。"),
    max_results: int | None = typer.Option(None, "--max-results", "-n", help="最大返回条数；默认读取 SEARCH_MAX_RESULTS。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """检索 arXiv 候选论文。"""
    configure_logging(verbose)
    try:
        candidates = discovery_search.search(query, start_year, end_year, max_results=max_results)
    except DiscoveryError as exc:
        logger.exception("search 执行失败") if verbose else logger.error("search 执行失败：%s", exc)
        raise typer.Exit(code=1) from exc
    for index, candidate in enumerate(candidates, start=1):
        print(f"[cyan]{index}. {candidate.title}[/cyan]")
        print(f"- arxiv_id: {candidate.arxiv_id}")
        print(f"- year: {candidate.year}")
        print(f"- authors: {', '.join(candidate.authors[:5])}")
        print(f"- url: {candidate.url}")


@app.command("fetch")
def fetch_paper(
    arxiv_id: str = typer.Argument(..., help="arXiv ID，例如 2401.12345。"),
    and_ingest: bool = typer.Option(False, "--and-ingest", help="源码落盘后立即运行 Layer1 ingest。"),
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="允许覆盖已有 raw/{slug}/。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """下载 arXiv PDF 和 LaTeX 源码到 raw/{slug}/。"""
    configure_logging(verbose)
    try:
        result = discovery_search.fetch(arxiv_id, and_ingest=and_ingest, overwrite=overwrite)
    except DiscoveryError as exc:
        logger.exception("fetch 执行失败：arxiv_id=%s", arxiv_id) if verbose else logger.error(
            "fetch 执行失败：%s",
            exc,
        )
        raise typer.Exit(code=1) from exc
    print("[green]Fetched paper successfully[/green]")
    print(f"- slug: {result.slug}")
    print(f"- raw_dir: {result.raw_dir}")
    print(f"- entry_file: {result.entry_file}")
    print(f"- has_pdf: {result.has_pdf}")
    print(f"- source_file_count: {result.source_file_count}")


@recommend_app.command("run")
def recommend_run(
    max_papers: int | None = typer.Option(None, "--max-papers", "-n", help="推荐 Top K 数量；默认读取 MAX_PAPER_NUM。"),
    arxiv_query: str | None = typer.Option(None, "--arxiv-query", help="覆盖 ARXIV_QUERY 候选池查询。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """生成 artifacts/.recommendations/ 下的每日推荐快照。"""
    configure_logging(verbose)
    try:
        snapshot = recommend_service.run(max_papers=max_papers, arxiv_query=arxiv_query)
    except (DiscoveryError, RecommendError) as exc:
        logger.exception("recommend run 执行失败") if verbose else logger.error("recommend run 执行失败：%s", exc)
        raise typer.Exit(code=1) from exc
    print("[green]Generated recommendations successfully[/green]")
    print(f"- date: {snapshot.date}")
    print(f"- corpus_size: {snapshot.corpus_size}")
    print(f"- candidate_pool_size: {snapshot.candidate_pool_size}")
    print(f"- candidates: {len(snapshot.candidates)}")
    print(f"- degraded: {snapshot.degraded}")


@graph_app.command("plan")
def graph_plan(
    slugs: list[str] | None = typer.Argument(None, help="一个或多个 reviewed artifacts/{slug} 目录名；与 --all 二选一。"),
    all_reviewed: bool = typer.Option(
        False, "--all", help="扫描 artifacts/ 下所有 meta_reviewed 且 prior_works_reviewed 的论文并全部 plan。"
    ),
    include_unreviewed: bool = typer.Option(False, "--include-unreviewed", help="允许为未 review 的 artifact 生成图谱事件。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """从 reviewed artifacts 生成 Layer2 图谱快照和增量 JSONL 事件。"""
    configure_logging(verbose)

    if all_reviewed:
        if slugs:
            print("[red]--all 不能与显式传入的 slug 同时使用[/red]")
            raise typer.Exit(code=1)
        try:
            slugs = discover_reviewed_slugs(get_settings().resolved_artifacts_dir())
        except Exception as exc:
            logger.exception("graph plan --all 扫描失败") if verbose else logger.error("graph plan --all 扫描失败：%s", exc)
            raise typer.Exit(code=1) from exc
        print(f"[cyan]Found {len(slugs)} reviewed paper(s) to plan.[/cyan]")
    elif not slugs:
        print("[red]请至少提供一个 slug，或使用 --all[/red]")
        raise typer.Exit(code=1)

    planner = _build_graph_planner()
    failures: list[str] = []

    for slug in slugs:
        try:
            result = planner.plan_slug(slug, include_unreviewed=include_unreviewed)
            print(f"[green]Planned graph updates for {slug}[/green]")
            print(f"- events: {len(result.events)}")
            print(f"- papers: {len(result.paper_keys)}")
            print(f"- relations: {len(result.relation_keys)}")
            print(f"- authors: {len(result.author_keys)}")
            print(f"- patterns: {len(result.pattern_ids)}")
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


@publish_app.command("render-html")
def render_html(
    slug: str = typer.Argument(..., help="artifacts/{slug} 目录名。"),
    theme: str | None = typer.Option(None, "--theme", help="排版主题；未传时使用 CURSOR_RENDER_THEME 默认值。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """调用本机 Cursor 无头模式，把 artifacts/{slug}/summary.md 排版成公众号 HTML。"""
    configure_logging(verbose)
    try:
        settings = get_settings()
        html_path = render_blog_html(slug, settings, theme=theme)
        PaperRepository(settings).mark_blog_html_generated(slug, html_path.name)
    except PublishingError as exc:
        logger.exception("publish render-html 执行失败：slug=%s", slug) if verbose else logger.error(
            "publish render-html 执行失败：%s",
            exc,
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        logger.exception("publish render-html 未预期失败：slug=%s", slug) if verbose else logger.error(
            "publish render-html 未预期失败：%s",
            exc,
        )
        raise typer.Exit(code=1) from exc

    print("[green]Blog HTML rendered successfully[/green]")
    print(f"- slug: {slug}")
    print(f"- html: {html_path.name}")


@publish_app.command("wechat")
def publish_wechat(
    slug: str = typer.Argument(..., help="artifacts/{slug} 目录名。"),
    html: str = typer.Option(..., "--html", help="artifacts/{slug}/ 下要发布的 HTML 文件名或相对路径。"),
    title: str | None = typer.Option(None, "--title", help="微信公众号草稿标题；未传时使用 HTML 文件名。"),
    author: str | None = typer.Option(None, "--author", help="微信公众号作者；未传时读取 WECHAT_AUTHOR。"),
    digest: str | None = typer.Option(None, "--digest", help="微信公众号摘要。"),
    cover: Path | None = typer.Option(None, "--cover", help="封面图路径；可传 artifact 内相对路径或项目根相对路径。"),
    thumb_media_id: str | None = typer.Option(None, "--thumb-media-id", help="已上传的封面永久素材 media_id。"),
    save_rendered: bool = typer.Option(False, "--save-rendered", help="保存图片 URL 替换后的 HTML 便于排查。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志和异常堆栈。"),
) -> None:
    """把 artifacts/{slug}/ 下的 HTML 创建为微信公众号草稿。"""
    configure_logging(verbose)
    try:
        settings = get_settings()
        result = publish_artifact_html_to_wechat(
            settings,
            WeChatDraftOptions(
                slug=slug,
                html_path=html,
                title=title,
                author=author,
                digest=digest,
                cover_path=cover,
                thumb_media_id=thumb_media_id,
                save_rendered=save_rendered,
            ),
        )
    except PublishingError as exc:
        logger.exception("publish wechat 执行失败：slug=%s", slug) if verbose else logger.error(
            "publish wechat 执行失败：%s",
            exc,
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        logger.exception("publish wechat 未预期失败：slug=%s", slug) if verbose else logger.error(
            "publish wechat 未预期失败：%s",
            exc,
        )
        raise typer.Exit(code=1) from exc

    print("[green]Created WeChat draft successfully[/green]")
    print(f"- slug: {result.slug}")
    print(f"- title: {result.title}")
    print(f"- media_id: {result.media_id}")
    print(f"- html: {result.html_path}")
    print(f"- uploaded images: {result.uploaded_image_count}")
    if result.rendered_html_path:
        print(f"- rendered html: {result.rendered_html_path}")


@app.command("web")
def serve_web(
    host: str = typer.Option("127.0.0.1", "--host", help="Web 服务监听地址。"),
    port: int = typer.Option(8000, "--port", help="Web 服务监听端口。"),
    reload: bool = typer.Option(False, "--reload", help="开发模式自动重载。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出 DEBUG 级别日志。"),
) -> None:
    """启动 Paper-Wiki Web 原型后端。"""
    from paper_wiki.web.middleware import configure_web_logging
    import uvicorn

    configure_web_logging(verbose)
    uvicorn.run("paper_wiki.web.app:app", host=host, port=port, reload=reload)


app.add_typer(publish_app, name="publish")
app.add_typer(graph_app, name="graph")
app.add_typer(recommend_app, name="recommend")


if __name__ == "__main__":
    app()
