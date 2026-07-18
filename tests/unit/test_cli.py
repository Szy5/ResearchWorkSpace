from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from paper_wiki.cli import main


def _fake_result(slug: str) -> SimpleNamespace:
    artifact_dir = Path("artifacts") / slug
    return SimpleNamespace(
        manifest_path=artifact_dir / "manifest.json",
        summary_path=artifact_dir / "summary.md",
        prior_works_path=artifact_dir / "prior_works.json",
        sci_pattern_path=artifact_dir / "sci_pattern.json",
        generated_paths={
            "summary": artifact_dir / "summary.md",
            "prior_works": artifact_dir / "prior_works.json",
            "sci_pattern": artifact_dir / "sci_pattern.json",
        },
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


def _write_graph_ready_artifacts(
    artifacts_dir: Path,
    slug: str,
    *,
    meta_reviewed: bool = True,
    prior_works_reviewed: bool = True,
) -> None:
    artifact_dir = artifacts_dir / slug
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "paper-wiki-assets-v1",
                "slug": slug,
                "created_at": "2026-07-16T00:00:00+00:00",
                "updated_at": "2026-07-16T00:00:00+00:00",
                "paper": {
                    "title": f"Paper {slug}",
                    "authors": ["Test Author"],
                    "abstract": "A test abstract.",
                    "year": 2025,
                    "venue": "TestConf",
                    "arxiv_id": f"2501.{slug}",
                    "meta_reviewed": meta_reviewed,
                    "prior_works_reviewed": prior_works_reviewed,
                    "added_date": "2026-07-16",
                },
                "source": {"raw_dir": f"raw/{slug}", "entry_file": "main.tex"},
                "counts": {"sections": 1, "figures": 0, "references": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "summary.md").write_text("# Test\n", encoding="utf-8")
    (artifact_dir / "prior_works.json").write_text(
        json.dumps(
            {
                "prior_works": [
                    {
                        "title": "Old Work",
                        "authors": "Ada Lovelace",
                        "year": 2010,
                        "arxiv_id": "1001.00001",
                        "role": "Foundation",
                        "relationship_sentence": "It defines the core idea.",
                    }
                ],
                "synthesis_narrative": "Builds on the foundational work.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "sci_pattern.json").write_text(
        json.dumps(
            {
                "primary_pattern": "P05",
                "primary_pattern_name": "Data & Evaluation Engineering",
                "secondary_patterns": [],
                "secondary_pattern_names": [],
                "confidence": "high",
                "reasoning": "Test reasoning.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_ingest_accepts_multiple_slugs(monkeypatch) -> None:
    calls: list[tuple[str, bool, str | None, str | None, str | None, list[str] | None]] = []

    class FakePipeline:
        def run(
            self,
            slug: str,
            overwrite: bool = False,
            *,
            summary_prompt: str | None = None,
            prior_works_prompt: str | None = None,
            sci_pattern_prompt: str | None = None,
            only: list[str] | None = None,
        ) -> SimpleNamespace:
            calls.append((slug, overwrite, summary_prompt, prior_works_prompt, sci_pattern_prompt, only))
            return _fake_result(slug)

    monkeypatch.setattr(main, "IngestPipeline", FakePipeline)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(
        main.app,
        ["ingest", "GraphWalker", "2508.00719", "--overwrite", "--summary-prompt", "paper_summary.py"],
    )

    assert result.exit_code == 0
    assert calls == [
        ("GraphWalker", True, "paper_summary.py", "prior_work_prompt.py", "sci_pattern_classify_prompt.py", None),
        ("2508.00719", True, "paper_summary.py", "prior_work_prompt.py", "sci_pattern_classify_prompt.py", None),
    ]
    assert "Generated Layer1 semantic artifacts for GraphWalker" in result.output
    assert "Generated Layer1 semantic artifacts for 2508.00719" in result.output


def test_ingest_only_passes_selected_artifact(monkeypatch) -> None:
    calls: list[list[str] | None] = []

    class FakePipeline:
        def run(
            self,
            slug: str,
            overwrite: bool = False,
            *,
            summary_prompt: str | None = None,
            prior_works_prompt: str | None = None,
            sci_pattern_prompt: str | None = None,
            only: list[str] | None = None,
        ) -> SimpleNamespace:
            calls.append(only)
            artifact_dir = Path("artifacts") / slug
            return SimpleNamespace(
                manifest_path=artifact_dir / "manifest.json",
                summary_path=artifact_dir / "summary.md",
                prior_works_path=artifact_dir / "prior_works.json",
                sci_pattern_path=artifact_dir / "sci_pattern.json",
                generated_paths={"sci_pattern": artifact_dir / "sci_pattern.json"},
            )

    monkeypatch.setattr(main, "IngestPipeline", FakePipeline)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["ingest", "GraphWalker", "--only", "pattern", "--overwrite"])

    assert result.exit_code == 0
    assert calls == [["pattern"]]
    assert "artifacts/GraphWalker/sci_pattern.json" in result.output
    assert "artifacts/GraphWalker/summary.md" not in result.output


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
            only: list[str] | None = None,
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
    assert "Generated Layer1 semantic artifacts for GraphWalker" in result.output
    assert "Failed to generate Layer1 semantic artifacts for 1 slug(s): broken-paper" in result.output


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
    calls: list[tuple[str, bool, str | None, str | None, str | None, list[str] | None]] = []

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
            only: list[str] | None = None,
        ) -> SimpleNamespace:
            calls.append((slug, overwrite, summary_prompt, prior_works_prompt, sci_pattern_prompt, only))
            return _fake_result(slug)

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(main, "IngestPipeline", FakePipeline)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["ingest-all", "--summary-prompt", "custom_summary.py"])

    assert result.exit_code == 0
    assert calls == [
        ("pending-paper", False, "custom_summary.py", "prior_work_prompt.py", "sci_pattern_classify_prompt.py", None)
    ]
    assert "Found 1 raw paper(s) to ingest." in result.output
    assert "Generated Layer1 semantic artifacts for pending-paper" in result.output


def test_discover_pending_slugs_with_only_checks_selected_artifact(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    artifacts_dir = tmp_path / "artifacts"
    raw_dir.mkdir()
    artifacts_dir.mkdir()
    _write_minimal_raw_paper(raw_dir, "summary-only")
    artifact_dir = artifacts_dir / "summary-only"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text("ok", encoding="utf-8")
    (artifact_dir / "summary.md").write_text("ok", encoding="utf-8")

    assert main.discover_pending_slugs(raw_dir, artifacts_dir, only=["summary"]) == []
    assert main.discover_pending_slugs(raw_dir, artifacts_dir, only=["pattern"]) == ["summary-only"]


def test_discover_reviewed_slugs_filters_by_both_review_flags(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    _write_graph_ready_artifacts(artifacts_dir, "fully-reviewed", meta_reviewed=True, prior_works_reviewed=True)
    _write_graph_ready_artifacts(artifacts_dir, "meta-only", meta_reviewed=True, prior_works_reviewed=False)
    _write_graph_ready_artifacts(artifacts_dir, "unreviewed", meta_reviewed=False, prior_works_reviewed=False)

    assert main.discover_reviewed_slugs(artifacts_dir) == ["fully-reviewed"]


def test_graph_plan_all_scans_and_plans_only_reviewed_papers(monkeypatch, tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    _write_graph_ready_artifacts(artifacts_dir, "paper-a")
    _write_graph_ready_artifacts(artifacts_dir, "paper-b")
    _write_graph_ready_artifacts(artifacts_dir, "paper-c", prior_works_reviewed=False)

    class FakeSettings:
        def resolved_artifacts_dir(self) -> Path:
            return artifacts_dir

        def resolved_graph_state_dir(self) -> Path:
            return tmp_path / "graph_state"

        def resolved_graph_updates_dir(self) -> Path:
            return tmp_path / "graph_updates"

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["graph", "plan", "--all"])

    assert result.exit_code == 0
    assert "Found 2 reviewed paper(s) to plan." in result.output
    assert "Planned graph updates for paper-a" in result.output
    assert "Planned graph updates for paper-b" in result.output
    assert "paper-c" not in result.output


def test_graph_plan_rejects_all_combined_with_explicit_slugs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["graph", "plan", "--all", "some-slug"])

    assert result.exit_code == 1
    assert "--all" in result.output


def test_graph_plan_requires_slugs_or_all(monkeypatch) -> None:
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["graph", "plan"])

    assert result.exit_code == 1
    assert "--all" in result.output


def test_assets_command_builds_multiple_slugs(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    class FakeAssetsBuilder:
        def build(self, slug: str, overwrite: bool = False) -> SimpleNamespace:
            calls.append((slug, overwrite))
            artifact_dir = Path("artifacts") / slug
            return SimpleNamespace(
                manifest_path=artifact_dir / "manifest.json",
                paper_path=artifact_dir / "assets" / "paper.md",
                sections_path=artifact_dir / "assets" / "sections.json",
                figures_manifest_path=artifact_dir / "assets" / "figures" / "manifest.json",
                references_path=artifact_dir / "assets" / "references.json",
            )

    monkeypatch.setattr(main, "PaperAssetsBuilder", FakeAssetsBuilder)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["assets", "GraphWalker", "2508.00719", "--overwrite"])

    assert result.exit_code == 0
    assert calls == [("GraphWalker", True), ("2508.00719", True)]
    assert "Generated assets for GraphWalker" in result.output
    assert "artifacts/GraphWalker/assets/paper.md" in result.output


def test_render_html_reports_missing_summary(monkeypatch, tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    (artifacts_dir / "GraphWalker").mkdir(parents=True)

    class FakeSettings:
        project_root = tmp_path
        cursor_headless_binary = "agent"
        cursor_headless_timeout_seconds = 5.0
        cursor_render_theme = "摸鱼绿"
        cursor_render_prompt_path = "blog_html_render_v1.py"

        def resolved_artifacts_dir(self) -> Path:
            return artifacts_dir

        def resolved_prompts_dir(self) -> Path:
            return Path("prompts")

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["publish", "render-html", "GraphWalker"])

    assert result.exit_code == 1


def test_render_html_prints_result_and_updates_manifest(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str | None]] = []

    class FakeSettings:
        pass

    def fake_render(slug: str, settings: FakeSettings, *, theme: str | None = None) -> Path:
        calls.append((slug, theme))
        return tmp_path / "summary.html"

    class FakeRepository:
        def __init__(self, settings: FakeSettings) -> None:
            pass

        def mark_blog_html_generated(self, slug: str, html_path: str) -> None:
            calls.append((slug, html_path))

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(main, "render_blog_html", fake_render)
    monkeypatch.setattr(main, "PaperRepository", FakeRepository)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(
        main.app,
        ["publish", "render-html", "GraphWalker", "--theme", "摸鱼绿"],
    )

    assert result.exit_code == 0
    assert calls == [("GraphWalker", "摸鱼绿"), ("GraphWalker", "summary.html")]
    assert "Blog HTML rendered successfully" in result.output
    assert "summary.html" in result.output


def test_publish_wechat_reports_missing_html(monkeypatch, tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    (artifacts_dir / "GraphWalker").mkdir(parents=True)

    class FakeSettings:
        project_root = tmp_path
        wechat_appid = "appid"
        wechat_secret = "secret"
        wechat_author = "Paper-Wiki"
        wechat_cover_path = None
        wechat_thumb_media_id = "thumb-media-id"
        wechat_request_timeout_seconds = 3.0

        def resolved_artifacts_dir(self) -> Path:
            return artifacts_dir

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(main.app, ["publish", "wechat", "GraphWalker", "--html", "missing.html"])

    assert result.exit_code == 1


def test_publish_wechat_prints_draft_result(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str | None]] = []

    class FakeSettings:
        pass

    def fake_publish(settings: FakeSettings, options: main.WeChatDraftOptions) -> SimpleNamespace:
        calls.append((options.slug, options.html_path, options.title))
        return SimpleNamespace(
            slug=options.slug,
            title=options.title or "Derived title",
            media_id="draft-media-id",
            html_path=tmp_path / "article.html",
            uploaded_image_count=3,
            rendered_html_path=tmp_path / "article_wechat_rendered.html",
        )

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(main, "publish_artifact_html_to_wechat", fake_publish)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(
        main.app,
        [
            "publish",
            "wechat",
            "GraphWalker",
            "--html",
            "article.html",
            "--title",
            "GraphWalker 论文精读",
            "--save-rendered",
        ],
    )

    assert result.exit_code == 0
    assert calls == [("GraphWalker", "article.html", "GraphWalker 论文精读")]
    assert "Created WeChat draft successfully" in result.output
    assert "draft-media-id" in result.output
    assert "uploaded images: 3" in result.output
