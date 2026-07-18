from __future__ import annotations

from pathlib import Path
import time

from fastapi.testclient import TestClient

from paper_wiki.core.config import Settings
from paper_wiki.publishing.models import WeChatDraftResult
from paper_wiki.web.app import create_app

from test_web_paper_repository import _write_demo_artifact


def _poll_job(client: TestClient, job_id: str) -> dict:
    job = {}
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.1)
    return job


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        raw_dir=tmp_path / "raw",
        artifacts_dir=tmp_path / "artifacts",
        prompts_dir=Path("prompts"),
        api_key="test",
        wechat_appid="appid",
        wechat_secret="secret",
    )


def test_web_routes_list_detail_and_conflict(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        papers = client.get("/api/papers").json()
        assert papers[0]["slug"] == "demo-paper"

        detail = client.get("/api/papers/demo-paper").json()
        assert detail["meta"]["title"] == "Demo Paper"

        conflict = client.patch(
            "/api/papers/demo-paper/meta",
            json={"expected_updated_at": "stale", "reviewed": True},
        )
        assert conflict.status_code == 409


def test_web_routes_publish_wechat(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    def fake_publish(settings: Settings, options, *, client=None) -> WeChatDraftResult:
        return WeChatDraftResult(
            slug=options.slug,
            title=options.title or "Demo",
            media_id="media-1",
            html_path=settings.resolved_artifacts_dir() / options.slug / options.html_path,
            thumb_media_id="thumb-1",
            uploaded_image_count=0,
        )

    monkeypatch.setattr("paper_wiki.web.routers.publish.publish_artifact_html_to_wechat", fake_publish)

    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/api/papers/demo-paper/publish/wechat",
            json={"html_path": "blog.html", "title": "Demo Draft"},
        )

    assert response.status_code == 200
    assert response.json()["media_id"] == "media-1"


def test_web_routes_render_blog_html_succeeds_and_records_manifest(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    def fake_render(slug: str, settings: Settings, *, theme: str | None = None) -> Path:
        assert theme == "摸鱼绿"
        html_path = settings.resolved_artifacts_dir() / slug / "summary.html"
        html_path.write_text("<section>ok</section>", encoding="utf-8")
        return html_path

    monkeypatch.setattr("paper_wiki.web.routers.publish.render_blog_html", fake_render)

    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/api/papers/demo-paper/blog/render-html",
            json={"theme": "摸鱼绿"},
        )
        assert response.status_code == 202
        job = _poll_job(client, response.json()["job_id"])
        assert job["status"] == "succeeded"
        assert job["result"]["html_path"] == "summary.html"

        detail = client.get("/api/papers/demo-paper").json()
        assert detail["meta"]["blog_html_path"] == "summary.html"
        assert detail["meta"]["blog_html_generated_at"] is not None


def test_web_routes_render_blog_html_reports_failure(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    def fake_render(slug: str, settings: Settings, *, theme: str | None = None) -> Path:
        from paper_wiki.publishing.exceptions import CursorRenderError

        raise CursorRenderError("summary.md 不存在")

    monkeypatch.setattr("paper_wiki.web.routers.publish.render_blog_html", fake_render)

    with TestClient(create_app(settings=settings)) as client:
        response = client.post("/api/papers/demo-paper/blog/render-html", json={})
        assert response.status_code == 202
        job = _poll_job(client, response.json()["job_id"])
        assert job["status"] == "failed"
        assert "summary.md" in job["error"]


def test_web_routes_reject_invalid_ingest_target(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/api/papers/demo-paper/ingest",
            json={"only": ["not-a-target"], "overwrite": True},
        )

    assert response.status_code == 422


def test_web_routes_serve_artifact_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_demo_artifact(settings.resolved_artifacts_dir())

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/papers/demo-paper/files/assets/figures/demo.png")
        fallback = client.get("/api/papers/demo-paper/files/figures/demo.png")
        traversal = client.get("/api/papers/demo-paper/files/../manifest.json")

    assert response.status_code == 200
    assert response.content == b"demo-image"
    assert fallback.status_code == 200
    assert fallback.content == b"demo-image"
    assert traversal.status_code in {400, 404}
