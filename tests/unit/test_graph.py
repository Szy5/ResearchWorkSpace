from __future__ import annotations

import json
from pathlib import Path

from paper_wiki.graph.artifact_reader import ArtifactReader
from paper_wiki.graph.planner import GraphPlanner, build_paper_key


def _write_reviewed_artifacts(artifacts_dir: Path, slug: str) -> None:
    artifact_dir = artifacts_dir / slug
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "summary.md").write_text(
        """---
slug: test-paper
title: Test Paper
authors:
  - Ada Lovelace
  - Alan Turing
year: 2024
venue: ICLR
arxiv_id: 2401.12345
reviewed: true
added_date: 2026-07-03
---

# Test Paper
""",
        encoding="utf-8",
    )
    (artifact_dir / "prior_works.json").write_text(
        json.dumps(
            {
                "prior_works": [
                    {
                        "title": "Prior Foundation Work",
                        "authors": "Grace Hopper, John McCarthy",
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

    assert bundle.summary.slug == "test-paper"
    assert bundle.prior_works.synthesis_narrative.startswith("The current work")
    assert bundle.sci_pattern.primary_pattern.value == "P05"


def test_graph_planner_generates_incremental_events(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    state_dir = tmp_path / "graph_state"
    updates_dir = tmp_path / "graph_updates"
    _write_reviewed_artifacts(artifacts_dir, "test-paper")

    planner = GraphPlanner(artifacts_dir, state_dir, updates_dir)
    result = planner.plan_slug("test-paper")

    assert len(result.events) == 3
    assert {event.op for event in result.events} == {
        "upsert_paper",
        "upsert_prior_work_relation",
    }
    assert build_paper_key("Test Paper", 2024, "2401.12345") in result.paper_keys
    assert (updates_dir / "graph_updates.jsonl").exists()
    assert (state_dir / "papers.json").exists()
    assert (state_dir / "prior_work_relations.json").exists()

    second_result = planner.plan_slug("test-paper")
    assert second_result.events == []


def test_graph_planner_emits_minimal_node_and_relation_payloads(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    state_dir = tmp_path / "graph_state"
    updates_dir = tmp_path / "graph_updates"
    _write_reviewed_artifacts(artifacts_dir, "test-paper")

    planner = GraphPlanner(artifacts_dir, state_dir, updates_dir)
    result = planner.plan_slug("test-paper")

    paper_event = next(event for event in result.events if event.op == "upsert_paper")
    relation_event = next(event for event in result.events if event.op == "upsert_prior_work_relation")

    assert "reviewed" not in paper_event.payload.model_dump()
    assert "updated_at" not in paper_event.payload.model_dump()
    assert "source_summary_path" not in paper_event.payload.model_dump()
    assert relation_event.payload.model_dump() == {
        "relation_key": relation_event.payload.relation_key,
        "relation_type": "FOUNDATION",
        "source_paper_key": relation_event.payload.source_paper_key,
        "target_paper_key": relation_event.payload.target_paper_key,
        "source_slug": "test-paper",
    }
