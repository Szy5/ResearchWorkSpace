from pathlib import Path

from paper_wiki.ingestion.latex_parser import LaTeXParser


def test_latex_parser_inlines_inputs_and_matches_sections() -> None:
    parsed = LaTeXParser(max_chars=5000).parse(Path("tests/fixtures/sample_paper"))

    assert parsed.title == "Tiny Graph Reasoning"
    assert parsed.authors == ["Ada Lovelace", "Alan Turing"]
    assert parsed.entry_file == "main.tex"
    assert parsed.source_files == ["main.tex", "sections/method.tex"]
    assert parsed.matched_sections["introduction"] is True
    assert parsed.matched_sections["method"] is True
    assert parsed.matched_sections["experiments"] is True
    assert "random-walk trajectories" in parsed.raw_text
    assert "The two-stage training pipeline" in parsed.raw_text


def test_latex_parser_includes_subsections_under_matched_section(tmp_path: Path) -> None:
    paper_dir = tmp_path / "subsection-paper"
    paper_dir.mkdir()
    (paper_dir / "main.tex").write_text(
        r"""
\documentclass{article}
\title{Subsection Paper}
\author{Test Author}
\begin{document}
\section{Our Framework}
Framework overview paragraph.
\subsection{Component A}
Details about component A.
\subsection{Component B}
Details about component B.
\section{Experiments}
Main experiment paragraph.
\subsection{Experimental Setup}
Dataset and metrics.
\end{document}
""".strip(),
        encoding="utf-8",
    )

    parsed = LaTeXParser(max_chars=10000).parse(paper_dir)

    assert parsed.matched_sections["method"] is True
    assert parsed.matched_sections["experiments"] is True
    assert "Framework overview paragraph." in parsed.raw_text
    assert "Details about component A." in parsed.raw_text
    assert "Details about component B." in parsed.raw_text
    assert "Dataset and metrics." in parsed.raw_text
