from __future__ import annotations

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
from paper_wiki.ingestion.agent.sandbox import PaperSandbox


def _setup_sandbox_dirs(tmp_path: Path) -> tuple[Path, Path]:
    raw_dir = tmp_path / "raw" / "demo"
    assets_dir = tmp_path / "artifacts" / "demo" / "assets"
    raw_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)

    (raw_dir / "main.tex").write_text(
        "\\section{Introduction}\n"
        "Demo intro.\n"
        "\\subsection{Motivation}\n"
        "\\input{tables/main_res}\n"
        "\\section{Appendix}\n"
        "Ablation table shows +4.2 F1.\n",
        encoding="utf-8",
    )
    (raw_dir / "tables").mkdir()
    (raw_dir / "tables" / "main_res.tex").write_text("Method A & 61.55 \\\\\n", encoding="utf-8")
    (raw_dir / "iclr2026").mkdir()
    (raw_dir / "iclr2026" / "extra.tex").write_text("Nested subdir content.\n", encoding="utf-8")
    (raw_dir / "natbib.sty").write_text("% style noise\n", encoding="utf-8")
    (raw_dir / "paper.pdf").write_bytes(b"%PDF-1.4 binary noise")

    paper_lines = ["# Demo Paper", "", "## Introduction", "Line A about routing."] + [
        f"Body line {i}: detailed explanation of the proposed method and experimental setup." for i in range(1, 26)
    ] + ["## Experiments", "Hit@1 improves from 54.09 to 61.55."]
    (assets_dir / "paper.md").write_text("\n".join(paper_lines) + "\n", encoding="utf-8")
    (assets_dir / "references.json").write_text('{"references": [{"key": "smith2021", "title": "Graph QA"}]}', encoding="utf-8")
    return raw_dir, tmp_path / "artifacts" / "demo"


def test_list_files_defaults_to_raw_and_filters_noise(tmp_path: Path) -> None:
    raw_dir, artifact_dir = _setup_sandbox_dirs(tmp_path)
    sandbox = PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir)

    default_output = sandbox.list_files()
    assert "raw/main.tex" in default_output
    assert "raw/tables/main_res.tex" in default_output
    assert "raw/iclr2026/extra.tex" in default_output
    assert "assets/paper.md" not in default_output
    assert "natbib.sty" not in default_output
    assert "paper.pdf" not in default_output

    all_output = sandbox.list_files("all")
    assert all_output.index("raw/main.tex") < all_output.index("assets/paper.md")


def test_read_lines_bounds_and_truncation(tmp_path: Path) -> None:
    raw_dir, artifact_dir = _setup_sandbox_dirs(tmp_path)
    sandbox = PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir, max_read_lines=10)

    chunk = sandbox.read_lines("assets/paper.md", start_line=1, end_line=25)
    assert "[assets/paper.md] lines 1-10 / 31" in chunk
    assert "L1: # Demo Paper" in chunk
    assert "L10: Body line 6" in chunk
    assert "truncated by limit" in chunk

    raw_chunk = sandbox.read_lines("raw/tables/main_res.tex", start_line=1, end_line=5)
    assert "L1: Method A & 61.55 \\\\" in raw_chunk

    oom = sandbox.read_lines("raw/main.tex", start_line=999)
    assert "exceeds total lines" in oom


def test_grep_files_defaults_to_raw_and_handles_invalid_regex(tmp_path: Path) -> None:
    raw_dir, artifact_dir = _setup_sandbox_dirs(tmp_path)
    sandbox = PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir, max_grep_matches=2)

    default_hits = sandbox.grep_files("Ablation")
    assert "raw/main.tex:L6" in default_hits

    table_hits = sandbox.grep_files("61\\.55", path="raw/tables")
    assert "raw/tables/main_res.tex:L1" in table_hits

    capped = sandbox.grep_files("Body line", path="assets/paper.md")
    assert "truncated at max 2" in capped

    bad = sandbox.grep_files("[unclosed")
    assert "Invalid regex" in bad


def test_sandbox_blocks_path_traversal_and_symlink_escape(tmp_path: Path) -> None:
    raw_dir, artifact_dir = _setup_sandbox_dirs(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret\n", encoding="utf-8")
    escape_link = raw_dir / "escape.tex"
    escape_link.symlink_to(secret)

    sandbox = PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir)

    assert "Error" in sandbox.dispatch("read_lines", {"path": "../secret.txt"})
    assert "Error" in sandbox.dispatch("read_lines", {"path": "/etc/passwd"})
    assert "Error" in sandbox.dispatch("read_lines", {"path": "raw/../../secret.txt"})
    assert "Error" in sandbox.dispatch("read_lines", {"path": "raw/escape.tex"})
    assert "escape.tex" not in sandbox.list_files("raw")


def test_build_initial_map_centers_on_raw_tex_outline_and_figures(tmp_path: Path) -> None:
    raw_dir, artifact_dir = _setup_sandbox_dirs(tmp_path)
    sandbox = PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir)

    manifest = AssetsManifest(
        slug="demo",
        created_at="2026-11-27T00:00:00+00:00",
        updated_at="2026-11-27T00:00:00+00:00",
        paper=PaperAssetMeta(title="Demo Paper", authors=["Alice"], abstract="Short abstract."),
        source=SourceProvenance(raw_dir="raw/demo", entry_file="main.tex"),
        counts=AssetCounts(sections=2, figures=1, references=1),
    )
    bundle = PaperAssetsBundle(
        slug="demo",
        artifact_dir=artifact_dir,
        manifest=manifest,
        paper_markdown="",
        sections=SectionsDoc(
            sections=[
                SectionAsset(id="sec-1", type="introduction", title="Introduction", level=1, order=1, text="Intro text"),
            ]
        ),
        figures=FiguresDoc(
            figures=[
                FigureAsset(
                    id="fig-1",
                    caption="Overview diagram",
                    source_path="fig1.png",
                    asset_path="assets/figures/fig1.png",
                    section_id="sec-1",
                )
            ]
        ),
        references=ReferencesDoc(),
    )

    initial_map = sandbox.build_initial_map(bundle)
    assert "推测主入口文件: `raw/main.tex`" in initial_map
    assert "raw/tables/main_res.tex" in initial_map
    assert "- sec `raw/main.tex:L1`: Introduction" in initial_map
    assert "subsec `raw/main.tex:L3`: Motivation" in initial_map
    assert "input `raw/main.tex:L4` -> `tables/main_res`" in initial_map
    assert "assets/figures/fig1.png" in initial_map
