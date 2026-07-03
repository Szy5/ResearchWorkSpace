from __future__ import annotations

from pathlib import Path

import fitz

from paper_wiki.ingestion.summary_figure_converter import (
    convert_pdf_first_page_to_jpg,
    convert_summary_pdf_figures,
    find_file_case_insensitive,
    resolve_source_pdf,
)


def _write_sample_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "paper-wiki figure test")
    doc.save(path)
    doc.close()


def test_find_file_case_insensitive(tmp_path: Path) -> None:
    figures_dir = tmp_path / "Figures"
    figures_dir.mkdir()
    pdf_path = figures_dir / "example.pdf"
    _write_sample_pdf(pdf_path)

    found = find_file_case_insensitive(tmp_path, Path("figures/example.pdf"))
    assert found == pdf_path.resolve()


def test_resolve_source_pdf_from_latex_relative_path(tmp_path: Path) -> None:
    slug = "sample-paper"
    raw_dir = tmp_path / "raw"
    paper_dir = raw_dir / slug / "Figures"
    paper_dir.mkdir(parents=True)
    pdf_path = paper_dir / "example.pdf"
    _write_sample_pdf(pdf_path)

    artifact_dir = tmp_path / "artifacts" / slug
    artifact_dir.mkdir(parents=True)
    summary_path = artifact_dir / "summary.md"
    summary_path.write_text("# demo\n", encoding="utf-8")

    resolved = resolve_source_pdf(
        "Figures/example.pdf",
        slug=slug,
        raw_dir=raw_dir,
        summary_path=summary_path,
    )
    assert resolved == pdf_path.resolve()


def test_resolve_source_pdf_from_rewritten_markdown_path(tmp_path: Path) -> None:
    slug = "sample-paper"
    raw_dir = tmp_path / "raw"
    paper_dir = raw_dir / slug / "figures"
    paper_dir.mkdir(parents=True)
    pdf_path = paper_dir / "overview.pdf"
    _write_sample_pdf(pdf_path)

    artifact_dir = tmp_path / "artifacts" / slug
    artifact_dir.mkdir(parents=True)
    summary_path = artifact_dir / "summary.md"
    summary_path.write_text("# demo\n", encoding="utf-8")

    resolved = resolve_source_pdf(
        f"../../raw/{slug}/figures/overview.pdf",
        slug=slug,
        raw_dir=raw_dir,
        summary_path=summary_path,
    )
    assert resolved == pdf_path.resolve()


def test_convert_pdf_first_page_to_jpg(tmp_path: Path) -> None:
    pdf_path = tmp_path / "plot.pdf"
    jpg_path = tmp_path / "plot.jpg"
    _write_sample_pdf(pdf_path)

    convert_pdf_first_page_to_jpg(pdf_path, jpg_path)

    assert jpg_path.is_file()
    assert jpg_path.stat().st_size > 0


def test_convert_summary_pdf_figures_updates_markdown(tmp_path: Path) -> None:
    slug = "2401.01335v3"
    raw_dir = tmp_path / "raw"
    figures_dir = raw_dir / slug / "Figures"
    figures_dir.mkdir(parents=True)
    pdf_path = figures_dir / "example.pdf"
    _write_sample_pdf(pdf_path)

    artifact_dir = tmp_path / "artifacts" / slug
    artifact_dir.mkdir(parents=True)
    summary_path = artifact_dir / "summary.md"
    summary_path.write_text(
        "# Demo\n\n![示例图](Figures/example.pdf)\n",
        encoding="utf-8",
    )

    result = convert_summary_pdf_figures(
        summary_path,
        slug=slug,
        raw_dir=raw_dir,
        artifact_dir=artifact_dir,
    )

    assert len(result.converted) == 1
    assert result.converted[0] == ("Figures/example.pdf", "figures/example.jpg")
    updated = summary_path.read_text(encoding="utf-8")
    assert "![示例图](figures/example.jpg)" in updated
    assert (artifact_dir / "figures" / "example.jpg").is_file()


def test_convert_summary_pdf_figures_skips_missing_pdf(tmp_path: Path) -> None:
    slug = "missing-fig"
    raw_dir = tmp_path / "raw"
    (raw_dir / slug).mkdir(parents=True)
    artifact_dir = tmp_path / "artifacts" / slug
    artifact_dir.mkdir(parents=True)
    summary_path = artifact_dir / "summary.md"
    original = "# Demo\n\n![missing](figures/not-found.pdf)\n"
    summary_path.write_text(original, encoding="utf-8")

    result = convert_summary_pdf_figures(
        summary_path,
        slug=slug,
        raw_dir=raw_dir,
        artifact_dir=artifact_dir,
    )

    assert result.converted == []
    assert len(result.skipped) == 1
    assert summary_path.read_text(encoding="utf-8") == original


def test_convert_summary_pdf_figures_skips_non_pdf_images(tmp_path: Path) -> None:
    slug = "png-only"
    raw_dir = tmp_path / "raw"
    (raw_dir / slug).mkdir(parents=True)
    artifact_dir = tmp_path / "artifacts" / slug
    artifact_dir.mkdir(parents=True)
    summary_path = artifact_dir / "summary.md"
    original = "# Demo\n\n![png](figs/plot.png)\n"
    summary_path.write_text(original, encoding="utf-8")

    result = convert_summary_pdf_figures(
        summary_path,
        slug=slug,
        raw_dir=raw_dir,
        artifact_dir=artifact_dir,
    )

    assert result.converted == []
    assert result.skipped == []
    assert summary_path.read_text(encoding="utf-8") == original
