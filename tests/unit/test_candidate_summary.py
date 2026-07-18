from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from paper_wiki.core.config import Settings
from paper_wiki.discovery.models import RankedCandidate, RecommendationSnapshot
from paper_wiki.web.services import candidate_summary


class _FakeLLM:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append(user)
        for title, response in self.responses.items():
            if title in user:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected prompt: {user}")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        raw_dir=tmp_path / "raw",
        artifacts_dir=tmp_path / "artifacts",
        prompts_dir=Path("prompts"),
    )


def _snapshot(candidates: list[RankedCandidate]) -> RecommendationSnapshot:
    return RecommendationSnapshot(
        date=date(2026, 7, 15),
        generated_at=datetime.now(timezone.utc),
        corpus_size=1,
        candidate_pool_size=len(candidates),
        candidates=candidates,
        degraded=False,
    )


def test_enrich_with_display_summary_writes_snapshot_with_summaries(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    candidates = [
        RankedCandidate(title="Paper A", abstract="alpha abstract", arxiv_id="2401.00001"),
        RankedCandidate(title="Paper B", abstract="beta abstract", arxiv_id="2401.00002"),
    ]
    snapshot = _snapshot(candidates)
    fake_llm = _FakeLLM({"Paper A": "Alpha 一句话摘要", "Paper B": "Beta 一句话摘要"})
    monkeypatch.setattr(candidate_summary, "build_llm_client", lambda settings: fake_llm)

    candidate_summary.enrich_with_display_summary(snapshot, settings)

    assert snapshot.candidates[0].display_summary == "Alpha 一句话摘要"
    assert snapshot.candidates[1].display_summary == "Beta 一句话摘要"
    assert len(fake_llm.calls) == 2

    latest = tmp_path / "artifacts" / ".recommendations" / "latest.json"
    assert "Alpha 一句话摘要" in latest.read_text(encoding="utf-8")


def test_enrich_with_display_summary_skips_failed_candidates(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    candidates = [
        RankedCandidate(title="Good Paper", abstract="ok", arxiv_id="2401.00003"),
        RankedCandidate(title="Bad Paper", abstract="fails", arxiv_id="2401.00004"),
    ]
    snapshot = _snapshot(candidates)
    fake_llm = _FakeLLM({"Good Paper": "生成成功", "Bad Paper": RuntimeError("boom")})
    monkeypatch.setattr(candidate_summary, "build_llm_client", lambda settings: fake_llm)

    candidate_summary.enrich_with_display_summary(snapshot, settings)

    assert snapshot.candidates[0].display_summary == "生成成功"
    assert snapshot.candidates[1].display_summary == ""


def test_enrich_with_display_summary_noop_on_empty_candidates(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    snapshot = _snapshot([])

    def fail_if_called(settings: Settings) -> None:
        raise AssertionError("build_llm_client should not be called for an empty snapshot")

    monkeypatch.setattr(candidate_summary, "build_llm_client", fail_if_called)

    candidate_summary.enrich_with_display_summary(snapshot, settings)

    assert not (tmp_path / "artifacts" / ".recommendations").exists()
