from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from paper_wiki.core.config import Settings
from paper_wiki.discovery import recommend
from paper_wiki.discovery.models import SearchCandidate, ZoteroCorpusEntry


def test_time_decay_weights_sum_to_one() -> None:
    weights = recommend._time_decay_weights(3)

    assert round(sum(weights), 10) == 1
    assert weights[0] > weights[1] > weights[2]


def test_rerank_degrades_when_model_fails(monkeypatch) -> None:
    candidates = [
        SearchCandidate(title="A", abstract="alpha"),
        SearchCandidate(title="B", abstract="beta"),
    ]
    corpus = [ZoteroCorpusEntry(title="C", abstract="corpus", date_added=datetime.now(timezone.utc))]

    class BrokenModel:
        def __init__(self, model_name: str) -> None:
            raise RuntimeError("missing torch")

    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", type("M", (), {"SentenceTransformer": BrokenModel}))

    ranked, degraded = recommend._rerank(candidates, corpus)

    assert degraded is True
    assert [candidate.title for candidate in ranked] == ["A", "B"]
    assert [candidate.score for candidate in ranked] == [0.0, 0.0]


def test_rerank_reason_wraps_title_in_quotes_not_book_marks(monkeypatch) -> None:
    candidates = [SearchCandidate(title="Candidate", abstract="graph reasoning")]
    corpus = [ZoteroCorpusEntry(title="Best Match", abstract="graph reasoning", date_added=datetime.now(timezone.utc))]

    class FakeModel:
        def __init__(self, model_name: str) -> None:
            pass

        def encode(self, texts: list[str]) -> list[list[float]]:
            return [[1.0] for _ in texts]

    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", type("M", (), {"SentenceTransformer": FakeModel}))

    ranked, degraded = recommend._rerank(candidates, corpus, model_name="does-not-matter")

    assert degraded is False
    assert '"Best Match"' in ranked[0].reason
    assert "《" not in ranked[0].reason
    assert "》" not in ranked[0].reason


def test_run_writes_recommendation_snapshot(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(project_root=tmp_path, raw_dir=tmp_path / "raw", artifacts_dir=tmp_path / "artifacts")
    candidates = [SearchCandidate(title="Candidate", abstract="graph reasoning", arxiv_id="2401.12345")]
    corpus = [ZoteroCorpusEntry(title="Corpus", abstract="graph reasoning", date_added=datetime.now(timezone.utc))]

    monkeypatch.setattr(recommend.search_facade, "zotero_corpus", lambda settings: corpus)
    monkeypatch.setattr(recommend.search_facade, "daily_candidates", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(recommend, "_rerank", lambda cands, corpus, model_name: ([recommend._ranked(cands[0], 9.5, "similar")], False))

    snapshot = recommend.run(max_papers=1, settings=settings)

    latest = tmp_path / "artifacts" / ".recommendations" / "latest.json"
    assert snapshot.candidates[0].score == 9.5
    assert latest.exists()
    assert '"candidate_pool_size": 1' in latest.read_text(encoding="utf-8")

