from pathlib import Path

from paper_wiki.core.config import Settings
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.pipeline import IngestPipeline


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
    assert result.prior_works_path.exists()
    assert result.sci_pattern_path.exists()
    assert "reviewed: false" in result.summary_path.read_text(encoding="utf-8")
    assert '"prior_works": [' in result.prior_works_path.read_text(encoding="utf-8")
    assert '"primary_pattern": "P05"' in result.sci_pattern_path.read_text(encoding="utf-8")
    assert '"target_slug"' not in result.prior_works_path.read_text(encoding="utf-8")
    assert '"target_title"' not in result.sci_pattern_path.read_text(encoding="utf-8")
