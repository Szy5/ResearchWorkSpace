from __future__ import annotations

import json
from pathlib import Path

from paper_wiki.graph.artifact_reader import ArtifactReader
from paper_wiki.graph.planner import GraphPlanner, build_author_key, build_paper_key


def _write_reviewed_artifacts(
    artifacts_dir: Path,
    slug: str,
    *,
    meta_reviewed: bool = True,
    prior_works_reviewed: bool = True,
    prior_work_authors: str = "Grace Hopper, John McCarthy",
) -> None:
    artifact_dir = artifacts_dir / slug
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "paper-wiki-assets-v1",
                "slug": "test-paper",
                "created_at": "2026-07-03T00:00:00+00:00",
                "updated_at": "2026-07-03T00:00:00+00:00",
                "paper": {
                    "title": "Test Paper",
                    "authors": ["Ada Lovelace", "Alan Turing"],
                    "abstract": "A test paper.",
                    "year": 2024,
                    "venue": "ICLR",
                    "arxiv_id": "2401.12345",
                    "meta_reviewed": meta_reviewed,
                    "prior_works_reviewed": prior_works_reviewed,
                    "added_date": "2026-07-03",
                },
                "source": {"raw_dir": "raw/test-paper", "entry_file": "main.tex"},
                "counts": {"sections": 1, "figures": 0, "references": 1},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "summary.md").write_text(
        "# Test Paper\n",
        encoding="utf-8",
    )
    (artifact_dir / "prior_works.json").write_text(
        json.dumps(
            {
                "prior_works": [
                    {
                        "title": "Prior Foundation Work",
                        "authors": prior_work_authors,
                        "year": 2020,
                        "arxiv_id": "2001.00001",
                        "role": "Foundation",
                        "relationship_sentence": "It defines the benchmark used by the current work.",
                    }
                ],
                "synthesis_narrative": "The current work extends an established benchmark lineage.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "sci_pattern.json").write_text(
        json.dumps(
            {
                "primary_pattern": "P05",
                "primary_pattern_name": "Data & Evaluation Engineering",
                "secondary_patterns": ["P04"],
                "secondary_pattern_names": ["Modular Pipeline Composition"],
                "confidence": "high",
                "reasoning": "It primarily builds a new evaluation and pipeline framing.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_artifact_reader_loads_reviewed_artifacts(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_reviewed_artifacts(artifacts_dir, "test-paper")

    bundle = ArtifactReader(artifacts_dir).load("test-paper")

    assert bundle.manifest.slug == "test-paper"
    assert bundle.manifest.paper.meta_reviewed is True
    assert bundle.manifest.paper.prior_works_reviewed is True
    assert bundle.prior_works.synthesis_narrative.startswith("The current work")
    assert bundle.sci_pattern.primary_pattern.value == "P05"


def test_graph_planner_generates_incremental_events(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    state_dir = tmp_path / "graph_state"
    updates_dir = tmp_path / "graph_updates"
    _write_reviewed_artifacts(artifacts_dir, "test-paper")

    planner = GraphPlanner(artifacts_dir, state_dir, updates_dir)
    result = planner.plan_slug("test-paper")

    # 2 papers (main + stub) + 1 relation + 4 authors (2 main + 2 stub) + 4 authorships
    # + 2 patterns (primary + secondary) + 2 pattern classifications
    assert len(result.events) == 15
    assert {event.op for event in result.events} == {
        "upsert_paper",
        "upsert_prior_work_relation",
        "upsert_author",
        "upsert_authorship",
        "upsert_pattern",
        "upsert_pattern_classification",
    }
    assert build_paper_key("Test Paper", 2024, "2401.12345") in result.paper_keys
    assert build_author_key("Ada Lovelace") in result.author_keys
    assert build_author_key("Grace Hopper") in result.author_keys
    assert set(result.pattern_ids) == {"P05", "P04"}
    assert (updates_dir / "graph_updates.jsonl").exists()
    assert (state_dir / "papers.json").exists()
    assert (state_dir / "prior_work_relations.json").exists()
    assert (state_dir / "authors.json").exists()
    assert (state_dir / "patterns.json").exists()
    assert (state_dir / "authorships.json").exists()
    assert (state_dir / "pattern_classifications.json").exists()

    second_result = planner.plan_slug("test-paper")
    assert second_result.events == []


def test_graph_planner_emits_minimal_node_and_relation_payloads(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    state_dir = tmp_path / "graph_state"
    updates_dir = tmp_path / "graph_updates"
    _write_reviewed_artifacts(artifacts_dir, "test-paper")

    planner = GraphPlanner(artifacts_dir, state_dir, updates_dir)
    result = planner.plan_slug("test-paper")

    paper_event = next(event for event in result.events if event.op == "upsert_paper" and not event.payload.is_stub)
    relation_event = next(event for event in result.events if event.op == "upsert_prior_work_relation")
    author_event = next(event for event in result.events if event.op == "upsert_author")
    pattern_event = next(event for event in result.events if event.op == "upsert_pattern")
    authorship_event = next(event for event in result.events if event.op == "upsert_authorship")
    primary_classification = next(
        event
        for event in result.events
        if event.op == "upsert_pattern_classification" and event.payload.role == "primary"
    )
    secondary_classification = next(
        event
        for event in result.events
        if event.op == "upsert_pattern_classification" and event.payload.role == "secondary"
    )

    paper_payload = paper_event.payload.model_dump()
    assert "authors" not in paper_payload
    assert "primary_pattern_id" not in paper_payload
    assert "secondary_pattern_ids" not in paper_payload
    assert "added_date" not in paper_payload
    assert "reviewed" not in paper_payload
    assert "updated_at" not in paper_payload
    assert "source_summary_path" not in paper_payload
    # Narrative fields are the documented exception to property minimization for Paper.
    assert paper_payload["abstract"] == "A test paper."
    assert paper_payload["synthesis_narrative"].startswith("The current work")
    assert paper_payload["sci_pattern_reason"]

    assert relation_event.payload.model_dump() == {
        "relation_key": relation_event.payload.relation_key,
        "relation_type": "FOUNDATION",
        "source_paper_key": relation_event.payload.source_paper_key,
        "target_paper_key": relation_event.payload.target_paper_key,
        "source_slug": "test-paper",
    }

    assert set(author_event.payload.model_dump().keys()) == {"author_key", "name"}
    assert set(pattern_event.payload.model_dump().keys()) == {"pattern_id", "name"}
    assert set(authorship_event.payload.model_dump().keys()) == {
        "relation_key",
        "author_key",
        "paper_key",
        "author_order",
        "source_slug",
    }
    assert primary_classification.payload.confidence == "high"
    assert secondary_classification.payload.confidence is None


def test_graph_planner_requires_both_review_flags(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    state_dir = tmp_path / "graph_state"
    updates_dir = tmp_path / "graph_updates"
    _write_reviewed_artifacts(artifacts_dir, "test-paper", meta_reviewed=True, prior_works_reviewed=False)

    planner = GraphPlanner(artifacts_dir, state_dir, updates_dir)

    try:
        planner.plan_slug("test-paper")
    except ValueError as exc:
        assert "not reviewed" in str(exc)
    else:
        raise AssertionError("expected ValueError when prior_works_reviewed is False")

    result = planner.plan_slug("test-paper", include_unreviewed=True)
    assert result.paper_keys


def test_prior_work_stub_skips_author_extraction_for_et_al(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    state_dir = tmp_path / "graph_state"
    updates_dir = tmp_path / "graph_updates"
    _write_reviewed_artifacts(artifacts_dir, "test-paper", prior_work_authors="Smith et al.")

    planner = GraphPlanner(artifacts_dir, state_dir, updates_dir)
    result = planner.plan_slug("test-paper")

    # Only the 2 main-paper authors should produce Author nodes; the truncated
    # "et al." prior-work author string must not create any Author/AUTHORED edges.
    author_events = [event for event in result.events if event.op == "upsert_author"]
    authorship_events = [event for event in result.events if event.op == "upsert_authorship"]
    assert len(author_events) == 2
    assert len(authorship_events) == 2
    assert build_author_key("Ada Lovelace") in result.author_keys
    assert build_author_key("Smith") not in result.author_keys


def test_build_author_key_normalizes_case_and_whitespace() -> None:
    assert build_author_key("John  Smith") == build_author_key("john smith") == "john smith"
