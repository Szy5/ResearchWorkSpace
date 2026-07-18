from __future__ import annotations

from pathlib import Path
import time

from fastapi.testclient import TestClient

from paper_wiki.core.config import Settings
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.pipeline import IngestPipeline
from paper_wiki.web.app import create_app


class FakeLLM(LLMClient):
    def complete(self, system: str, user: str) -> str:
        return "# Tiny Graph Reasoning\n\n## 贡献\n- Uses staged training."


def test_web_ingest_job_flow(tmp_path: Path) -> None:
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
    )

    def pipeline_factory() -> IngestPipeline:
        return IngestPipeline(settings=settings, llm=FakeLLM())

    with TestClient(create_app(settings=settings, pipeline_factory=pipeline_factory)) as client:
        response = client.post(
            "/api/papers/sample_paper/ingest",
            json={"only": ["summary"], "overwrite": True},
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        for _ in range(50):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.1)
        assert job["status"] == "succeeded"

        detail = client.get("/api/papers/sample_paper").json()
        assert detail["meta"]["title"] == "Tiny Graph Reasoning"
        assert detail["summary"].startswith("# Tiny Graph Reasoning")
