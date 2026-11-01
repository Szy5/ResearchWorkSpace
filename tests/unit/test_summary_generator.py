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


def test_number_figure_captions_merges_italic_caption_lines() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = (
        "Text.\n\n![短](assets/figures/a.jpg)\n\n*图：完整的中文图注*\n\nMore.\n\n"
        "![图 7：已有编号](assets/figures/b.jpg)\n"
    )
    numbered = generator._number_figure_captions(content)
    assert "![图 1：完整的中文图注](assets/figures/a.jpg)" in numbered
    assert "*图：" not in numbered
    assert "![图 2：已有编号](assets/figures/b.jpg)" in numbered


class _PlacementLLM:
    def __init__(self, placements: list[dict[str, str]]) -> None:
        self.placements = placements
        self.calls = 0

    def complete_json(self, system: str, user: str, schema):  # type: ignore[no-untyped-def]
        self.calls += 1
        return schema.model_validate({"placements": self.placements})


def test_supplement_figures_inserts_chosen_figure_at_section_end() -> None:
    llm = _PlacementLLM(
        [
            {"path": "assets/figures/unknown.jpg", "heading": "整体框架", "caption": "不存在的图"},
            {"path": "assets/figures/graphwalker_overview.jpg", "heading": "整体框架", "caption": "图 9：GraphWalker 整体流程"},
        ]
    )
    generator = SummaryGenerator(llm, prompts_dir=None)  # type: ignore[arg-type]
    summary = "# T\n\n## 方法详解\n\n### 整体框架\n\n框架说明。\n\n### 关键设计\n\n设计说明。\n"

    result = generator._number_figure_captions(generator._supplement_figures(summary, _bundle()))

    assert llm.calls == 1
    assert "unknown.jpg" not in result
    assert "框架说明。\n\n![图 1：GraphWalker 整体流程](assets/figures/graphwalker_overview.jpg)\n\n### 关键设计" in result


def test_supplement_figures_skips_llm_when_enough_figures() -> None:
    llm = _PlacementLLM([])
    generator = SummaryGenerator(llm, prompts_dir=None)  # type: ignore[arg-type]
    summary = "# T\n\n## 方法\n\n![图 1：概览](assets/figures/graphwalker_overview.jpg)\n"

    assert generator._supplement_figures(summary, _bundle()) == summary
    assert llm.calls == 0
