from pathlib import Path

import pytest

from paper_wiki.core.config import Settings
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.pipeline import IngestPipeline
from paper_wiki.ingestion import prior_works_backfill


@pytest.fixture(autouse=True)
def _no_network_prior_works_backfill(monkeypatch):
    """这些测试只验证 pipeline 编排本身，先前工作的 arXiv 回填单独在
    test_prior_works_backfill.py 里覆盖；这里桩掉网络请求，保持无候选、行为与接入前一致。"""
    monkeypatch.setattr(prior_works_backfill.discovery_search, "search", lambda *args, **kwargs: [])


class FakeLLM(LLMClient):
    def complete(self, system: str, user: str) -> str:
        if "prior_works" in user:
            return """
            {
              "prior_works": [
                {
                  "title": "Graph QA Foundations",
                  "authors": "Smith et al.",
                  "year": 2021,
                  "arxiv_id": "",
                  "role": "Foundation",
                  "relationship_sentence": "It defines the graph QA setup extended by the current work."
                }
              ],
              "synthesis_narrative": "Graph QA Foundations established the evaluation setup and path reasoning framing. The current work builds from that framing by adding staged trajectory synthesis."
            }
            """
        if '"classifications"' in user:
            return """
            {
              "classifications": [
                {
                  "paper_index": 1,
                  "primary_pattern": "P05",
                  "secondary_patterns": ["P04"],
                  "confidence": "high",
                  "reasoning": "The paper centers on synthetic trajectories and evaluation for graph reasoning agents."
                }
              ]
            }
            """
        return "# Tiny Graph Reasoning\n\n## 2. 贡献\n**类型**：方法改进型\n- Uses staged training."


def test_pipeline_writes_layer1_artifacts(tmp_path: Path) -> None:
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
    )

    result = IngestPipeline(settings=settings, llm=FakeLLM()).run("sample_paper", overwrite=True)

    assert result.summary_path.exists()
    assert result.manifest_path is not None
    assert result.manifest_path.exists()
    assert result.assets.title == "Tiny Graph Reasoning"
    assert (result.artifact_dir / "assets" / "paper.md").exists()
    assert (result.artifact_dir / "assets" / "sections.json").exists()
    assert (result.artifact_dir / "assets" / "figures" / "manifest.json").exists()
    assert (result.artifact_dir / "assets" / "references.json").exists()
    assert result.prior_works_path.exists()
    assert result.sci_pattern_path.exists()
    summary_text = result.summary_path.read_text(encoding="utf-8")
    assert summary_text.startswith("# Tiny Graph Reasoning")
    assert not summary_text.startswith("---")
    assert "## 语义分析补充" not in summary_text
    assert "## 科学发现范式" in summary_text
    assert "P05 Data & Evaluation Engineering" in summary_text
    assert "置信度" not in summary_text
    assert "The paper centers on synthetic trajectories" in summary_text
    assert "## 先前工作分析" in summary_text
    assert "Graph QA Foundations established" in summary_text
    assert '"reviewed": false' in result.manifest_path.read_text(encoding="utf-8")
    assert '"prior_works": [' in result.prior_works_path.read_text(encoding="utf-8")
    assert '"primary_pattern": "P05"' in result.sci_pattern_path.read_text(encoding="utf-8")
    assert '"target_slug"' not in result.prior_works_path.read_text(encoding="utf-8")
    assert '"target_title"' not in result.sci_pattern_path.read_text(encoding="utf-8")


def test_pipeline_can_generate_one_semantic_artifact(tmp_path: Path) -> None:
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
    )

    result = IngestPipeline(settings=settings, llm=FakeLLM()).run(
        "sample_paper",
        overwrite=True,
        only=["summary"],
    )

    assert result.summary_path.exists()
    assert result.generated_paths == {"summary": result.summary_path}
    assert not result.prior_works_path.exists()
    assert not result.sci_pattern_path.exists()
    assert "## 科学发现范式" not in result.summary_path.read_text(encoding="utf-8")


def test_pipeline_backfills_prior_works_from_arxiv(tmp_path: Path, monkeypatch) -> None:
    from paper_wiki.discovery.models import SearchCandidate

    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
    )
    matched = SearchCandidate(
        title="Graph QA Foundations",
        authors=["Alice Smith", "Bob Lee"],
        year=2021,
        arxiv_id="2101.00001",
    )
    monkeypatch.setattr(
        prior_works_backfill.discovery_search, "search", lambda *args, **kwargs: [matched]
    )

    result = IngestPipeline(settings=settings, llm=FakeLLM()).run("sample_paper", overwrite=True)

    prior_works_text = result.prior_works_path.read_text(encoding="utf-8")
    assert '"arxiv_id": "2101.00001"' in prior_works_text
    assert '"authors": "Alice Smith, Bob Lee"' in prior_works_text


def test_pipeline_enriches_summary_from_existing_semantic_artifacts(tmp_path: Path) -> None:
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
    )
    pipeline = IngestPipeline(settings=settings, llm=FakeLLM())
    pipeline.run("sample_paper", overwrite=True)

    result = pipeline.run("sample_paper", overwrite=True, only=["summary"])
    summary_text = result.summary_path.read_text(encoding="utf-8")

    assert result.generated_paths == {"summary": result.summary_path}
    assert "## 科学发现范式" in summary_text
    assert "P05 Data & Evaluation Engineering" in summary_text
    assert "## 先前工作分析" in summary_text
    assert "Graph QA Foundations established" in summary_text
