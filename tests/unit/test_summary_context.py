from pathlib import Path

from paper_wiki.assets.models import (
    AssetCounts,
    AssetsManifest,
    FigureAsset,
    FiguresDoc,
    PaperAssetMeta,
    PaperAssetsBundle,
    ReferencesDoc,
    SectionAsset,
    SectionsDoc,
    SourceProvenance,
)
from paper_wiki.ingestion.generators.summary_context import build_summary_context, compact_tables

TABLE = r"""**Table: Main results.**

```latex
\begin{table}[t]
\centering
\resizebox{\columnwidth}{!}{
\begin{tabular}{@{}l*{2}{c}@{}}
\toprule
\multicolumn{3}{@{}l}{Group} \\
Method & F1 & EM \\
\midrule
Ours & \textbf{65.53} & $\checkmark$ \\
Base & 60.10 & 50.0\% \\
\bottomrule
\end{tabular}}
\end{table}
```"""


def _section(order: int, sid: str, title: str, text: str, *, parent: str = "", figs: list[str] | None = None) -> SectionAsset:
    return SectionAsset(
        id=sid,
        type="subsection" if parent else ("abstract" if sid == "sec-abstract" else "section"),
        title=title,
        level=2 if parent else 1,
        order=order,
        parent_id=parent,
        text=text,
        figure_ids=figs or [],
    )


def _bundle() -> PaperAssetsBundle:
    sections = [
        _section(0, "sec-abstract", "Abstract", "We study X."),
        _section(1, "sec-intro", "Introduction", "Intro text."),
        _section(2, "sec-method", "Method", "Method overview."),
        _section(3, "sec-method-a", "Menu Environment", "Details of the menu.", parent="sec-method"),
        _section(4, "sec-exp", "Experiments", ""),
        _section(5, "sec-exp-main", "Main Results", "Results text.\n\n" + TABLE, parent="sec-exp"),
        _section(6, "sec-conc", "Conclusion", "We conclude."),
        _section(7, "sec-lim", "Limitations", "Text only."),
        _section(8, "sec-app", "Implementation Details", "Appendix secret."),
    ]
    figures = [
        FigureAsset(id="fig-fw", caption="Framework overview.", source_path="figures/fw.pdf", asset_path="assets/figures/fw.jpg", section_id="sec-method"),
        FigureAsset(id="fig-case", caption="Appendix case.", source_path="figures/case.pdf", asset_path="assets/figures/case.jpg", section_id="sec-app"),
    ]
    return PaperAssetsBundle(
        slug="demo",
        artifact_dir=Path("artifacts/demo"),
        manifest=AssetsManifest(
            slug="demo",
            created_at="2026-07-13T00:00:00+00:00",
            updated_at="2026-07-13T00:00:00+00:00",
            paper=PaperAssetMeta(title="Demo", abstract="We study X."),
            source=SourceProvenance(raw_dir="raw/demo", entry_file="main.tex"),
            counts=AssetCounts(sections=len(sections), figures=len(figures), references=0),
        ),
        paper_markdown="# Demo\n",
        sections=SectionsDoc(sections=sections),
        figures=FiguresDoc(figures=figures),
        references=ReferencesDoc(),
    )


def test_compact_tables_turns_latex_into_pipe_rows() -> None:
    compact = compact_tables(TABLE)
    assert "```" not in compact
    assert "[TABLE]" in compact
    assert "【Group】" in compact and "@" not in compact
    assert "Ours: F1=**65.53**; EM=✓" in compact
    assert "Base: F1=60.10; EM=50.0%" in compact


def test_summary_context_keeps_subsections_and_skips_appendix() -> None:
    context = build_summary_context(_bundle())
    assert "Details of the menu." in context
    assert "Ours: F1=**65.53**" in context
    assert "Text only." in context
    assert "Appendix secret." not in context
    assert "assets/figures/fw.jpg" in context and "Framework overview." in context
    assert "assets/figures/case.jpg" not in context


def test_summary_context_trims_long_sections_but_keeps_tables() -> None:
    bundle = _bundle()
    bundle.sections.sections[1].text = "\n\n".join(["Long intro paragraph. " * 20] * 40)
    bundle.sections.sections[5].text = "\n\n".join(["Result paragraph. " * 20] * 20) + "\n\n" + TABLE
    context = build_summary_context(bundle, max_chars=9000)
    assert len(context) < 12000
    assert "[……本节其余内容已省略]" in context
    assert "Details of the menu." in context
    assert "Ours: F1=**65.53**" in context


def test_compact_tables_labels_multilevel_headers_and_marker_macros() -> None:
    table = r"""```latex
\begin{tabular}{lcccc}
\toprule
& \multicolumn{2}{c}{2Wiki} & \multicolumn{2}{c}{HotpotQA} \\
Method & F1 & G-E & F1 & G-E \\
\midrule
\multicolumn{5}{@{}l}{\textit{Qwen2.5-3B}} \\
\Marker{\A}{\B}Naive generation & 7.59 & 55.00 & 11.16 & 53.75 \\
\end{tabular}
```"""
    compact = compact_tables(table)
    assert "【Qwen2.5-3B】" in compact
    assert "Naive generation: 2Wiki F1=7.59; 2Wiki G-E=55.00; HotpotQA F1=11.16; HotpotQA G-E=53.75" in compact
