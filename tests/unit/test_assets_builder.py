from __future__ import annotations

from pathlib import Path

import fitz

from paper_wiki.assets.builder import PaperAssetsBuilder
from paper_wiki.assets.reader import AssetsReader
from paper_wiki.core.config import Settings


def _create_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "asset figure")
    doc.save(path)
    doc.close()


def test_assets_builder_writes_minimal_contract(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    artifacts_dir = tmp_path / "artifacts"
    paper_dir = raw_dir / "demo-paper"
    figure_dir = paper_dir / "figures"
    figure_dir.mkdir(parents=True)
    _create_pdf(figure_dir / "overview.pdf")
    (paper_dir / "refs.bib").write_text(
        r"""
@inproceedings{smith2024demo,
  title = {Demo Reference},
  author = {Smith, Ada and Turing, Alan},
  year = {2024},
  booktitle = {DemoConf},
  url = {https://example.com/demo}
}
""".strip(),
        encoding="utf-8",
    )
    (paper_dir / "main.tex").write_text(
        r"""
\documentclass{article}
\title{Demo Paper}
\author{Ada Lovelace and Alan Turing}
\begin{document}
\begin{abstract}
We study a demo problem.
\end{abstract}
\section{Introduction}
Prior work matters \citep{smith2024demo}.
\begin{figure}
\centering
\includegraphics{figures/overview.pdf}
\caption{Overview figure.}
\label{fig:overview}
\end{figure}
\section{Method}
We propose a method
that spans source lines.
\begin{equation}
\mathcal{L} = \frac{1}{N}\sum_i x_i
\end{equation}
\begin{tcolorbox}[title=Prompt]
Line one.

Line two.
\end{tcolorbox}
\begin{table}
\caption{Main results.}
\begin{tabular}{lc}
Method & Score \\
Ours & 1.0 \\
\end{tabular}
\label{tab:main}
\end{table}
\bibliography{refs}
\end{document}
""".strip(),
        encoding="utf-8",
    )

    settings = Settings(
        project_root=tmp_path,
        raw_dir=raw_dir,
        artifacts_dir=artifacts_dir,
        prompts_dir=Path("prompts"),
        api_key="test",
    )
    result = PaperAssetsBuilder(settings=settings).build("demo-paper", overwrite=True)

    assert result.manifest_path.is_file()
    assert result.paper_path.is_file()
    assert result.sections_path.is_file()
    assert result.figures_manifest_path.is_file()
    assert result.references_path.is_file()
    assert (result.figures_dir / "overview.jpg").is_file()
    paper = result.paper_path.read_text(encoding="utf-8")
    assert "# Demo Paper" in paper
    assert "![Overview figure.](figures/overview.jpg)" in paper
    assert r"\![" not in paper
    assert "Prior work matters [smith2024demo]." in paper
    assert "We propose a method that spans source lines." in paper
    assert r"\mathcal{L} = \frac{1}{N}\sum_i x_i" in paper
    assert "**LaTeX block: tcolorbox**" in paper
    assert r"\begin{tcolorbox}[title=Prompt]" in paper
    assert "Line one.\n\nLine two." in paper
    assert "```latex" in paper
    assert r"\begin{tabular}{lc}" in paper
    assert '"title": "Introduction"' in result.sections_path.read_text(encoding="utf-8")
    assert '"caption": "Overview figure."' in result.figures_manifest_path.read_text(encoding="utf-8")
    references = result.references_path.read_text(encoding="utf-8")
    assert '"key": "smith2024demo"' in references
    assert '"title": "Demo Reference"' in references
    manifest = result.manifest_path.read_text(encoding="utf-8")
    assert '"summary"' not in manifest
    assert '"prior_works"' not in manifest
    assert '"sci_pattern"' not in manifest


def test_assets_reader_loads_existing_assets_as_bundle(tmp_path: Path) -> None:
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
    )
    builder = PaperAssetsBuilder(settings=settings)
    builder.build("sample_paper", overwrite=True)

    bundle = AssetsReader(settings=settings).load("sample_paper")

    assert bundle.title == "Tiny Graph Reasoning"
    assert bundle.entry_file == "main.tex"
    assert bundle.matched_sections["method"] is True
    assert "random-walk trajectories" in bundle.llm_context()
