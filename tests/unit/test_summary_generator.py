from paper_wiki.ingestion.generators.summary_generator import SummaryGenerator


class _DummyLLM:
    pass


def test_rewrite_figure_paths_from_latex_relative_path() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = "![overview](figures/graphwalker_overview.pdf)\n\nSome text."
    rewritten = generator._rewrite_figure_paths(content, "GraphWalker")
    assert rewritten == (
        "![overview](../../raw/GraphWalker/figures/graphwalker_overview.pdf)\n\nSome text."
    )


def test_rewrite_figure_paths_handles_capitalized_figures_dir() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = "![example](Figures/example.pdf)"
    rewritten = generator._rewrite_figure_paths(content, "2401.01335v3")
    assert rewritten == "![example](../../raw/2401.01335v3/Figures/example.pdf)"


def test_rewrite_figure_paths_skips_absolute_and_already_rewritten() -> None:
    generator = SummaryGenerator(_DummyLLM(), prompts_dir=None)  # type: ignore[arg-type]
    content = (
        "![a](https://example.com/a.png)\n"
        "![b](../../raw/GraphWalker/figures/b.pdf)\n"
        "![c](figures/c.pdf)"
    )
    rewritten = generator._rewrite_figure_paths(content, "GraphWalker")
    assert "https://example.com/a.png" in rewritten
    assert "![b](../../raw/GraphWalker/figures/b.pdf)" in rewritten
    assert "![c](../../raw/GraphWalker/figures/c.pdf)" in rewritten
