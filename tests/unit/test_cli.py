from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from paper_wiki.cli import main


def _fake_result(slug: str) -> SimpleNamespace:
    artifact_dir = Path("artifacts") / slug
    return SimpleNamespace(
        summary_path=artifact_dir / "summary.md",
        prior_works_path=artifact_dir / "prior_works.json",
        sci_pattern_path=artifact_dir / "sci_pattern.json",
    )


def _write_minimal_raw_paper(raw_dir: Path, slug: str) -> None:
    paper_dir = raw_dir / slug
    paper_dir.mkdir(parents=True)
    (paper_dir / "main.tex").write_text(r"\begin{document}Tiny paper\end{document}", encoding="utf-8")


def _write_complete_artifacts(artifacts_dir: Path, slug: str) -> None:
    artifact_dir = artifacts_dir / slug
    artifact_dir.mkdir(parents=True)
    for filename in main.LAYER1_ARTIFACT_FILES:
        (artifact_dir / filename).write_text("ok", encoding="utf-8")


def test_ingest_accepts_multiple_slugs(monkeypatch) -> None:
    calls: list[tuple[str, bool, str | None, str | None, str | None]] = []

    class FakePipeline:
        def run(
            self,
            slug: str,
            overwrite: bool = False,
            *,
            summary_prompt: str | None = None,
            prior_works_prompt: str | None = None,
            sci_pattern_prompt: str | None = None,
        ) -> SimpleNamespace:
            calls.append((slug, overwrite, summary_prompt, prior_works_prompt, sci_pattern_prompt))
            return _fake_result(slug)

    monkeypatch.setattr(main, "IngestPipeline", FakePipeline)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(
        main.app,
        ["ingest", "GraphWalker", "2508.00719", "--overwrite", "--summary-prompt", "paper_summary.py"],
    )

    assert result.exit_code == 0
    assert calls == [
        ("GraphWalker", True, "paper_summary.py", "prior_work_prompt.py", "sci_pattern_classify_prompt.py"),
        ("2508.00719", True, "paper_summary.py", "prior_work_prompt.py", "sci_pattern_classify_prompt.py"),
    ]
    assert "Generated Layer1 artifacts for GraphWalker" in result.output
    assert "Generated Layer1 artifacts for 2508.00719" in result.output


def test_ingest_continues_after_one_slug_fails(monkeypatch) -> None:
    calls: list[str] = []

    class FakePipeline:
        def run(
            self,
            slug: str,
            overwrite: bool = False,
            *,
            summary_prompt: str | None = None,
            prior_works_prompt: str | None = None,
            sci_pattern_prompt: str | None = None,
        ) -> SimpleNamespace:
            calls.append(slug)
            if slug == "broken-paper":
                raise ValueError("cannot parse")
            return _fake_result(slug)

    monkeypatch.setattr(main, "IngestPipeline", FakePipeline)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["ingest", "broken-paper", "GraphWalker"])

    assert result.exit_code == 1
    assert calls == ["broken-paper", "GraphWalker"]
    assert "Generated Layer1 artifacts for GraphWalker" in result.output
    assert "Failed to generate Layer1 artifacts for 1 slug(s): broken-paper" in result.output


def test_discover_pending_slugs_skips_complete_artifacts(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    artifacts_dir = tmp_path / "artifacts"
    raw_dir.mkdir()
    artifacts_dir.mkdir()
    _write_minimal_raw_paper(raw_dir, "complete-paper")
    _write_minimal_raw_paper(raw_dir, "pending-paper")
    (raw_dir / "notes-only").mkdir()
    (raw_dir / "notes-only" / "README.md").write_text("not a paper", encoding="utf-8")
    _write_complete_artifacts(artifacts_dir, "complete-paper")

    assert main.discover_pending_slugs(raw_dir, artifacts_dir) == ["pending-paper"]
    assert main.discover_pending_slugs(raw_dir, artifacts_dir, overwrite=True) == [
        "complete-paper",
        "pending-paper",
    ]


def test_ingest_all_discovers_and_runs_pending_slugs(monkeypatch, tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    artifacts_dir = tmp_path / "artifacts"
    raw_dir.mkdir()
    artifacts_dir.mkdir()
    _write_minimal_raw_paper(raw_dir, "complete-paper")
    _write_minimal_raw_paper(raw_dir, "pending-paper")
    _write_complete_artifacts(artifacts_dir, "complete-paper")
    calls: list[tuple[str, bool, str | None, str | None, str | None]] = []

    class FakeSettings:
        def resolved_raw_dir(self) -> Path:
            return raw_dir

        def resolved_artifacts_dir(self) -> Path:
            return artifacts_dir

    class FakePipeline:
        def run(
            self,
            slug: str,
            overwrite: bool = False,
            *,
            summary_prompt: str | None = None,
            prior_works_prompt: str | None = None,
            sci_pattern_prompt: str | None = None,
        ) -> SimpleNamespace:
            calls.append((slug, overwrite, summary_prompt, prior_works_prompt, sci_pattern_prompt))
            return _fake_result(slug)

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(main, "IngestPipeline", FakePipeline)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["ingest-all", "--summary-prompt", "custom_summary.py"])

    assert result.exit_code == 0
    assert calls == [
        ("pending-paper", False, "custom_summary.py", "prior_work_prompt.py", "sci_pattern_classify_prompt.py")
    ]
    assert "Found 1 raw paper(s) to ingest." in result.output
    assert "Generated Layer1 artifacts for pending-paper" in result.output
