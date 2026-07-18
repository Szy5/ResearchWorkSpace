from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from paper_wiki.assets.models import (
    AssetCounts,
    AssetsManifest,
    PaperAssetMeta,
    SourceProvenance,
)
from paper_wiki.core.config import Settings
from paper_wiki.web.services.paper_repository import PaperConflictError, PaperRepository


def _write_demo_artifact(artifacts_dir: Path, slug: str = "demo-paper") -> None:
    artifact_dir = artifacts_dir / slug
    (artifact_dir / "assets" / "figures").mkdir(parents=True)
    manifest = AssetsManifest(
        slug=slug,
        created_at="2026-07-14T00:00:00+00:00",
        updated_at="2026-07-14T00:00:00+00:00",
        paper=PaperAssetMeta(
            title="Demo Paper",
            authors=["Ada Lovelace"],
            abstract="A compact demo artifact.",
            year=2026,
            venue="DemoConf",
            reviewed=False,
            added_date=date(2026, 7, 14),
        ),
        source=SourceProvenance(raw_dir=f"raw/{slug}", entry_file="main.tex"),
        counts=AssetCounts(sections=1, figures=0, references=1),
    )
    (artifact_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    (artifact_dir / "assets" / "paper.md").write_text("# Demo Paper\n", encoding="utf-8")
    (artifact_dir / "assets" / "sections.json").write_text('{"sections": []}', encoding="utf-8")
    (artifact_dir / "assets" / "figures" / "demo.png").write_bytes(b"demo-image")
    (artifact_dir / "assets" / "figures" / "manifest.json").write_text('{"figures": []}', encoding="utf-8")
    (artifact_dir / "assets" / "references.json").write_text(
        '{"references": [{"key": "demo", "title": "Demo Reference"}]}',
        encoding="utf-8",
    )
    (artifact_dir / "summary.md").write_text("# Summary\n", encoding="utf-8")
    (artifact_dir / "prior_works.json").write_text(
        """
{
  "prior_works": [
    {
      "title": "Prior Demo",
      "authors": "Turing",
      "year": 2024,
      "arxiv_id": "",
      "role": "Foundation",
      "relationship_sentence": "It frames the demo."
    }
  ],
  "synthesis_narrative": "Prior Demo frames the demo."
}
""".strip(),
        encoding="utf-8",
    )
    (artifact_dir / "sci_pattern.json").write_text(
        '{"primary_pattern": "P05", "primary_pattern_name": "Data & Evaluation Engineering", '
        '"confidence": "high", "reasoning": "It builds data."}',
        encoding="utf-8",
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        raw_dir=tmp_path / "raw",
        artifacts_dir=tmp_path / "artifacts",
        prompts_dir=Path("prompts"),
        api_key="test",
    )


def test_repository_lists_and_loads_papers(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    repository = PaperRepository(settings)
    items = repository.list_papers()
    detail = repository.get_paper("demo-paper")

    assert [item.slug for item in items] == ["demo-paper"]
    assert items[0].primary_pattern == "P05"
    assert detail.meta.title == "Demo Paper"
    assert detail.summary.startswith("# Summary")
    assert detail.references_count == 1


def test_repository_rejects_stale_updates(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())
    repository = PaperRepository(settings)

    with pytest.raises(PaperConflictError):
        repository.update_meta("demo-paper", {"reviewed": True}, expected_updated_at="stale")


def test_repository_marks_blog_html_generated(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())
    repository = PaperRepository(settings)

    detail = repository.mark_blog_html_generated("demo-paper", "summary.html")

    assert detail.meta.blog_html_path == "summary.html"
    assert detail.meta.blog_html_generated_at is not None

    refreshed = repository.get_paper("demo-paper")
    assert refreshed.meta.blog_html_path == "summary.html"


def test_repository_validates_slug(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    with pytest.raises(ValueError):
        PaperRepository(settings).get_paper("../demo-paper")


def test_repository_updates_summary_and_manifest_timestamp(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())
    repository = PaperRepository(settings)
    detail = repository.get_paper("demo-paper")

    updated = repository.update_summary("demo-paper", "New summary", expected_updated_at=detail.updated_at)

    assert updated.summary == "New summary\n"
    assert updated.updated_at != detail.updated_at


def test_repository_derives_reviewed_from_both_sub_flags(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())
    repository = PaperRepository(settings)
    detail = repository.get_paper("demo-paper")
    assert detail.meta.reviewed is False

    after_meta = repository.update_meta(
        "demo-paper", {"meta_reviewed": True}, expected_updated_at=detail.updated_at
    )
    assert after_meta.meta.meta_reviewed is True
    assert after_meta.meta.reviewed is False, "only one of the two sub-flags is set so far"

    after_prior_works = repository.update_meta(
        "demo-paper", {"prior_works_reviewed": True}, expected_updated_at=after_meta.updated_at
    )
    assert after_prior_works.meta.prior_works_reviewed is True
    assert after_prior_works.meta.reviewed is True, "both sub-flags are now set"


def test_legacy_manifest_with_reviewed_true_implicitly_migrates_sub_flags(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())
    manifest_path = settings.resolved_artifacts_dir() / "demo-paper" / "manifest.json"
    legacy_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    legacy_manifest["paper"]["reviewed"] = True
    manifest_path.write_text(json.dumps(legacy_manifest), encoding="utf-8")

    detail = PaperRepository(settings).get_paper("demo-paper")

    assert detail.meta.reviewed is True
    assert detail.meta.meta_reviewed is True
    assert detail.meta.prior_works_reviewed is True
