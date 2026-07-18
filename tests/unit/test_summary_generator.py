from pathlib import Path

from paper_wiki.assets.models import (
    AssetCounts,
    AssetsManifest,
    FigureAsset,
    FiguresDoc,
    PaperAssetMeta,
    PaperAssetsBundle,
    ReferencesDoc,
    SectionsDoc,
    SourceProvenance,
)
from paper_wiki.ingestion.generators.summary_generator import SummaryGenerator


class _DummyLLM:
    pass


def _bundle() -> PaperAssetsBundle:
    return PaperAssetsBundle(
        slug="GraphWalker",
        artifact_dir=Path("artifacts/GraphWalker"),
        manifest=AssetsManifest(
            slug="GraphWalker",
            created_at="2026-07-13T00:00:00+00:00",
            updated_at="2026-07-13T00:00:00+00:00",
            paper=PaperAssetMeta(title="GraphWalker"),
            source=SourceProvenance(raw_dir="raw/GraphWalker", entry_file="main.tex"),
            counts=AssetCounts(sections=0, figures=1, references=0),
        ),
        paper_markdown="# GraphWalker\n",
        sections=SectionsDoc(),
        figures=FiguresDoc(
            figures=[
                FigureAsset(
                    id="fig-overview",
                    label="fig:overview",
                    caption="Overview",
                    source_path="figures/graphwalker_overview.pdf",
                    asset_path="assets/figures/graphwalker_overview.jpg",
                    status="rendered",
                )
            ]
        ),
        references=ReferencesDoc(),
    )


def test_rewrite_figure_paths_from_latex_relative_path() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = "![overview](figures/graphwalker_overview.pdf)\n\nSome text."
    rewritten = generator._rewrite_figure_paths(content, _bundle())
    assert rewritten == "![overview](assets/figures/graphwalker_overview.jpg)\n\nSome text."


def test_rewrite_figure_paths_handles_asset_relative_path() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = "![example](figures/graphwalker_overview.jpg)"
    rewritten = generator._rewrite_figure_paths(content, _bundle())
    assert rewritten == "![example](assets/figures/graphwalker_overview.jpg)"


def test_rewrite_figure_paths_skips_absolute_and_already_rewritten() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = (
        "![a](https://example.com/a.png)\n"
        "![b](assets/figures/graphwalker_overview.jpg)\n"
        "![c](figures/graphwalker_overview.pdf)"
    )
    rewritten = generator._rewrite_figure_paths(content, _bundle())
    assert "https://example.com/a.png" in rewritten
    assert "![b](assets/figures/graphwalker_overview.jpg)" in rewritten
    assert "![c](assets/figures/graphwalker_overview.jpg)" in rewritten


def test_clean_summary_content_strips_model_frontmatter() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = """---
title: Model Metadata
reviewed: false
---

# GraphWalker

Body.
"""

    cleaned = generator._clean_summary_content(content)

    assert cleaned == "# GraphWalker\n\nBody.\n"
