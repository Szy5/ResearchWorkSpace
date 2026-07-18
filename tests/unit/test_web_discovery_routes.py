from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import time

from fastapi.testclient import TestClient

from paper_wiki.core.config import Settings
from paper_wiki.discovery.models import FetchResult, RankedCandidate, RecommendationSnapshot, SearchCandidate
from paper_wiki.web.app import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        raw_dir=tmp_path / "raw",
        artifacts_dir=tmp_path / "artifacts",
        prompts_dir=Path("prompts"),
        api_key="test",
    )


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    job: dict = {}
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    return job


def test_recommendations_today_returns_null_when_missing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/recommendations/today")
    assert response.status_code == 200
    assert response.json() is None


def test_recommendations_today_reads_latest_snapshot(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    output_dir = settings.resolved_artifacts_dir() / ".recommendations"
    output_dir.mkdir(parents=True)
    snapshot = RecommendationSnapshot(
        date=date(2026, 7, 14),
        generated_at=datetime.now(timezone.utc),
        corpus_size=3,
        candidate_pool_size=5,
        candidates=[],
        degraded=False,
    )
    (output_dir / "latest.json").write_text(snapshot.model_dump_json(), encoding="utf-8")

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/recommendations/today")

    assert response.status_code == 200
    assert response.json()["corpus_size"] == 3


def test_recommendations_refresh_submits_job_and_writes_result(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    snapshot = RecommendationSnapshot(
        date=date(2026, 7, 14),
        generated_at=datetime.now(timezone.utc),
        corpus_size=1,
        candidate_pool_size=1,
        candidates=[],
        degraded=False,
    )
    monkeypatch.setattr(
        "paper_wiki.web.routers.recommendations.recommend_service.run",
        lambda **kwargs: snapshot,
    )
    monkeypatch.setattr(
        "paper_wiki.web.routers.recommendations.candidate_summary.enrich_with_display_summary",
        lambda snapshot, settings: None,
    )

    with TestClient(create_app(settings=settings)) as client:
        response = client.post("/api/recommendations/refresh", json={})
        assert response.status_code == 202
        job = _wait_for_job(client, response.json()["job_id"])

    assert job["status"] == "succeeded"
    assert job["result"]["corpus_size"] == 1


def test_recommendations_refresh_enriches_candidates_with_display_summary(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    snapshot = RecommendationSnapshot(
        date=date(2026, 7, 14),
        generated_at=datetime.now(timezone.utc),
        corpus_size=1,
        candidate_pool_size=1,
        candidates=[RankedCandidate(title="A candidate", abstract="abstract", arxiv_id="2401.00001")],
        degraded=False,
    )
    monkeypatch.setattr(
        "paper_wiki.web.routers.recommendations.recommend_service.run",
        lambda **kwargs: snapshot,
    )

    def fake_enrich(snap, settings) -> None:
        for candidate in snap.candidates:
            candidate.display_summary = f"summary for {candidate.title}"

    monkeypatch.setattr(
        "paper_wiki.web.routers.recommendations.candidate_summary.enrich_with_display_summary",
        fake_enrich,
    )

    with TestClient(create_app(settings=settings)) as client:
        response = client.post("/api/recommendations/refresh", json={})
        job = _wait_for_job(client, response.json()["job_id"])

    assert job["status"] == "succeeded"
    assert job["result"]["candidates"][0]["display_summary"] == "summary for A candidate"


def test_search_endpoint_delegates_to_discovery(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    candidates = [SearchCandidate(title="Attention Is All You Need", arxiv_id="1706.03762")]
    monkeypatch.setattr(
        "paper_wiki.web.routers.search.discovery_search.search",
        lambda query, start_year, end_year, max_results=None, settings=None: candidates,
    )

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/search", params={"q": "attention"})

    assert response.status_code == 200
    assert response.json()[0]["arxiv_id"] == "1706.03762"


def test_fetch_endpoint_submits_job_and_reports_slug(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    fetch_result = FetchResult(
        slug="2401.12345",
        raw_dir=tmp_path / "raw" / "2401.12345",
        entry_file="main.tex",
        has_pdf=True,
        source_file_count=2,
    )
    monkeypatch.setattr(
        "paper_wiki.web.routers.papers.discovery_search.fetch",
        lambda arxiv_id, *, and_ingest=False, overwrite=False, settings=None: fetch_result,
    )

    with TestClient(create_app(settings=settings)) as client:
        response = client.post("/api/papers/fetch", json={"arxiv_id": "2401.12345"})
        assert response.status_code == 202
        job = _wait_for_job(client, response.json()["job_id"])

    assert job["status"] == "succeeded"
    assert job["result"]["slug"] == "2401.12345"


def test_batch_ingest_rejects_ambiguous_item(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/api/papers/batch-ingest",
            json={"items": [{"arxiv_id": "2401.12345", "slug": "already-local"}]},
        )
    assert response.status_code == 422


def test_batch_ingest_fans_out_slug_and_arxiv_id_jobs(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    fetch_result = FetchResult(
        slug="2401.12345",
        raw_dir=tmp_path / "raw" / "2401.12345",
        entry_file="main.tex",
        has_pdf=True,
        source_file_count=2,
    )
    monkeypatch.setattr(
        "paper_wiki.web.routers.papers.discovery_search.fetch",
        lambda arxiv_id, *, and_ingest=False, overwrite=False, settings=None: fetch_result,
    )

    from test_web_paper_repository import _write_demo_artifact

    _write_demo_artifact(settings.resolved_artifacts_dir(), slug="already-local")

    calls: list[str] = []

    def fake_pipeline_factory():
        class FakePipeline:
            def run(self, slug: str, **kwargs: object) -> None:
                calls.append(slug)

        return FakePipeline()

    with TestClient(create_app(settings=settings, pipeline_factory=fake_pipeline_factory)) as client:
        response = client.post(
            "/api/papers/batch-ingest",
            json={"items": [{"arxiv_id": "2401.12345"}, {"slug": "already-local"}]},
        )
        assert response.status_code == 202
        jobs = response.json()
        assert len(jobs) == 2
        for job in jobs:
            settled = _wait_for_job(client, job["job_id"])
            assert settled["status"] == "succeeded"

    assert calls == ["already-local"]
