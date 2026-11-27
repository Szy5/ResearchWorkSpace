from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from paper_wiki.cli import main
from paper_wiki.core.config import Settings
from paper_wiki.ingestion.agent.loop import PaperAgentLoop
from paper_wiki.ingestion.agent.sandbox import PaperSandbox
from paper_wiki.ingestion.agent.summary_agent import AgentSummaryGenerator
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.ingestion.pipeline import IngestPipeline


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


class _FakeCompletionClient:
    """Scripted OpenAI-compatible client recording all requests."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        # Deep-copy messages snapshot so later mutations don't hide per-step history.
        snapshot = dict(kwargs)
        snapshot["messages"] = json.loads(json.dumps(kwargs["messages"]))
        self.requests.append(snapshot)
        return self._responses.pop(0)


class _UnusedLLM(LLMClient):
    def complete(self, system: str, user: str) -> str:
        raise AssertionError("workflow single-shot LLM should not be called for agent summary")


def _make_response(
    *,
    content: str = "",
    tool_calls: list[_FakeToolCall] | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cached_tokens: int = 0,
    deepseek_style_cache: bool = False,
) -> SimpleNamespace:
    if deepseek_style_cache:
        usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_cache_hit_tokens=cached_tokens,
        )
    else:
        usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
        )
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def test_agent_loop_parallel_tools_prompt_cache_and_usage(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "p1"
    artifact_dir = tmp_path / "artifacts" / "p1"
    (artifact_dir / "assets").mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    (artifact_dir / "assets" / "paper.md").write_text("# Title\nLine 2: Hit@1 is 61.55.\n", encoding="utf-8")
    (raw_dir / "main.tex").write_text("Appendix: cost is 2x.\n", encoding="utf-8")

    fake_client = _FakeCompletionClient(
        [
            _make_response(
                content="",
                tool_calls=[
                    _FakeToolCall("tc-1", "read_lines", '{"path": "assets/paper.md", "start_line": 1, "end_line": 10}'),
                    _FakeToolCall("tc-2", "grep_files", '{"pattern": "cost", "path": "raw"}'),
                    _FakeToolCall("tc-3", "read_lines", "not-valid-json"),
                ],
                prompt_tokens=500,
                completion_tokens=60,
                cached_tokens=0,
                deepseek_style_cache=True,
            ),
            _make_response(
                content="# Title\n\n## 问题与动机\n作者提出了新方法，Hit@1 达到 61.55。",
                prompt_tokens=800,
                completion_tokens=200,
                cached_tokens=450,
                deepseek_style_cache=True,
            ),
        ]
    )
    settings = Settings(
        project_root=Path.cwd(),
        api_key="test",
        model_name="deepseek-chat",
        langsmith_tracing=False,
        langsmith_api_key=None,
    )
    sandbox = PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir)
    loop = PaperAgentLoop(settings=settings, client=fake_client, max_steps=6)

    result = loop.run(
        slug="p1",
        system_prompt="SYS",
        initial_user_prompt="USER_MAP",
        sandbox=sandbox,
    )

    assert result.steps == 2
    assert "61.55" in result.content
    assert result.usage.llm_calls == 2
    assert result.usage.tool_calls == 3
    assert result.usage.prompt_tokens == 1300
    assert result.usage.cached_tokens == 450
    assert result.usage.completion_tokens == 260
    assert result.trace_id is None

    # Verify append-only prefix preservation for prompt caching.
    assert fake_client.requests[0]["messages"][:2] == fake_client.requests[1]["messages"][:2]
    tool_messages = [m for m in fake_client.requests[1]["messages"] if m["role"] == "tool"]
    assert len(tool_messages) == 3
    assert "Hit@1 is 61.55." in tool_messages[0]["content"]
    assert "cost is 2x." in tool_messages[1]["content"]
    assert "Invalid JSON arguments" in tool_messages[2]["content"]


def test_agent_loop_assembles_streaming_tool_calls_and_cache_write_usage(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "p_stream"
    artifact_dir = tmp_path / "artifacts" / "p_stream"
    raw_dir.mkdir(parents=True)
    (artifact_dir / "assets").mkdir(parents=True)
    (raw_dir / "main.tex").write_text("Accuracy is 77.6%.\n", encoding="utf-8")

    def _chunk(content: str = "", tool_calls: list[Any] | None = None, usage: Any = None) -> SimpleNamespace:
        delta = SimpleNamespace(content=content, tool_calls=tool_calls or [])
        return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)

    stream_step_1 = [
        _chunk(
            tool_calls=[
                SimpleNamespace(index=0, id="tc-s1", type="function", function=SimpleNamespace(name="read_", arguments='{"path":'))
            ]
        ),
        _chunk(
            tool_calls=[
                SimpleNamespace(index=0, id=None, type=None, function=SimpleNamespace(name="lines", arguments=' "raw/main.tex"}'))
            ]
        ),
        SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                prompt_tokens=1000,
                completion_tokens=40,
                total_tokens=1040,
                prompt_tokens_details=SimpleNamespace(cached_tokens=200, cache_write_tokens=750),
            ),
        ),
    ]
    stream_step_2 = [
        _chunk(content="# Search-RSI\n\n"),
        _chunk(content="27B 达到 77.6%。"),
        SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                prompt_tokens=1400,
                completion_tokens=90,
                total_tokens=1490,
                prompt_tokens_details=SimpleNamespace(cached_tokens=950, cache_write_tokens=400),
            ),
        ),
    ]
    fake_client = _FakeCompletionClient([stream_step_1, stream_step_2])
    settings = Settings(
        project_root=Path.cwd(),
        api_key="test",
        model_name="claude-sonnet-5-5",
        langsmith_tracing=False,
        langsmith_api_key=None,
    )
    loop = PaperAgentLoop(settings=settings, client=fake_client, max_steps=4, stream=True)
    result = loop.run(
        slug="p_stream",
        system_prompt="SYS",
        initial_user_prompt="MAP",
        sandbox=PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir),
    )

    assert result.steps == 2
    assert "77.6%" in result.content
    assert result.usage.tool_calls == 1
    assert result.usage.cached_tokens == 1150
    assert result.usage.cache_write_tokens == 1150
    assert fake_client.requests[0]["stream"] is True
    assert fake_client.requests[0]["stream_options"] == {"include_usage": True}


def test_agent_loop_forces_final_answer_at_max_steps(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "p2"
    artifact_dir = tmp_path / "artifacts" / "p2"
    (artifact_dir / "assets").mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    (artifact_dir / "assets" / "paper.md").write_text("# Paper\nBody.\n", encoding="utf-8")

    fake_client = _FakeCompletionClient(
        [
            _make_response(
                tool_calls=[_FakeToolCall("tc-1", "list_files", '{"scope": "all"}')],
                prompt_tokens=200,
                completion_tokens=20,
            ),
            _make_response(
                content="# Paper\n\nFinal synthesis after step budget reached.",
                prompt_tokens=300,
                completion_tokens=80,
                cached_tokens=180,
            ),
        ]
    )
    settings = Settings(
        project_root=Path.cwd(),
        api_key="test",
        langsmith_tracing=False,
        langsmith_api_key=None,
    )
    loop = PaperAgentLoop(settings=settings, client=fake_client, max_steps=2)
    result = loop.run(
        slug="p2",
        system_prompt="SYS",
        initial_user_prompt="MAP",
        sandbox=PaperSandbox(raw_dir=raw_dir, artifact_dir=artifact_dir),
    )

    assert result.steps == 2
    assert "tools" in fake_client.requests[0]
    assert "tools" not in fake_client.requests[1]
    assert "最大检索步数" in fake_client.requests[1]["messages"][-1]["content"]
    assert result.usage.cached_tokens == 180


def test_pipeline_agent_mode_generates_cleaned_summary_and_keeps_raw_readonly(tmp_path: Path) -> None:
    fake_client = _FakeCompletionClient(
        [
            _make_response(
                tool_calls=[_FakeToolCall("tc-1", "read_lines", '{"path": "assets/paper.md", "start_line": 1, "end_line": 80}')],
                prompt_tokens=400,
                completion_tokens=40,
            ),
            _make_response(
                content=(
                    "```markdown\n"
                    "---\ntitle: should be stripped\n---\n"
                    "# Tiny Graph Reasoning\n\n"
                    "## 问题与动机\n"
                    "我们提出了分阶段路径推理。\n"
                    "```"
                ),
                prompt_tokens=700,
                completion_tokens=120,
                cached_tokens=350,
            ),
        ]
    )
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
        langsmith_tracing=False,
        langsmith_api_key=None,
    )
    pipeline = IngestPipeline(settings=settings, llm=_UnusedLLM())
    agent_loop = PaperAgentLoop(settings=settings, client=fake_client, max_steps=5)
    pipeline._agent_summary_generator = AgentSummaryGenerator(
        pipeline.summary_generator,
        settings=settings,
        agent_loop=agent_loop,
    )

    result = pipeline.run("sample_paper", overwrite=True, only=["summary"], mode="agent")

    assert result.summary_path.exists()
    summary_text = result.summary_path.read_text(encoding="utf-8")
    assert summary_text.startswith("# Tiny Graph Reasoning")
    assert not summary_text.startswith("---")
    assert "作者提出了分阶段路径推理" in summary_text
    assert result.agent_stats is not None
    assert result.agent_stats["mode"] == "agent"
    assert result.agent_stats["steps"] == 2
    assert result.agent_stats["tool_calls"] == 1
    assert result.agent_stats["cached_tokens"] == 350


def test_pipeline_uses_settings_ingest_mode_by_default(tmp_path: Path) -> None:
    fake_client = _FakeCompletionClient(
        [
            _make_response(
                content="# Tiny Graph Reasoning\n\n## 问题与动机\n由 INGEST_MODE=agent 默认触发。",
                prompt_tokens=300,
                completion_tokens=60,
            ),
        ]
    )
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
        ingest_mode="agent",
        langsmith_tracing=False,
        langsmith_api_key=None,
    )
    pipeline = IngestPipeline(settings=settings, llm=_UnusedLLM())
    pipeline._agent_summary_generator = AgentSummaryGenerator(
        pipeline.summary_generator,
        settings=settings,
        agent_loop=PaperAgentLoop(settings=settings, client=fake_client, max_steps=3),
    )

    result = pipeline.run("sample_paper", overwrite=True, only=["summary"])

    assert result.agent_stats is not None
    assert result.agent_stats["mode"] == "agent"
    assert "INGEST_MODE=agent" in result.summary_path.read_text(encoding="utf-8")


def test_pipeline_rejects_invalid_mode(tmp_path: Path) -> None:
    settings = Settings(
        project_root=Path.cwd(),
        raw_dir=Path("tests/fixtures"),
        artifacts_dir=tmp_path,
        prompts_dir=Path("prompts"),
        api_key="test",
        langsmith_tracing=False,
    )
    pipeline = IngestPipeline(settings=settings, llm=_UnusedLLM())
    with pytest.raises(ValueError, match="Unknown ingest mode"):
        pipeline.run("sample_paper", overwrite=True, only=["summary"], mode="invalid")


def test_cli_ingest_agent_mode_forwards_mode_and_default_prompt(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    class FakeAgentPipeline:
        def run(self, slug: str, overwrite: bool = False, **kwargs: Any) -> SimpleNamespace:
            captured.append({"slug": slug, "overwrite": overwrite, **kwargs})
            artifact_dir = Path("artifacts") / slug
            return SimpleNamespace(
                manifest_path=artifact_dir / "manifest.json",
                summary_path=artifact_dir / "summary.md",
                prior_works_path=artifact_dir / "prior_works.json",
                sci_pattern_path=artifact_dir / "sci_pattern.json",
                generated_paths={"summary": artifact_dir / "summary.md"},
                agent_stats={
                    "steps": 3,
                    "tool_calls": 4,
                    "prompt_tokens": 1200,
                    "cached_tokens": 600,
                    "completion_tokens": 300,
                    "trace_id": "trace-abc-123",
                },
            )

    monkeypatch.setattr(main, "IngestPipeline", FakeAgentPipeline)
    monkeypatch.setattr(main, "configure_logging", lambda verbose: None)

    result = CliRunner().invoke(
        main.app,
        ["ingest", "2402.11163", "--only", "summary", "--mode", "agent", "--overwrite"],
    )

    assert result.exit_code == 0
    assert len(captured) == 1
    assert captured[0]["mode"] == "agent"
    assert captured[0]["summary_prompt"] == "paper_summary_agent_v1.py"
    assert "trace_id=trace-abc-123" in result.output

    bad = CliRunner().invoke(main.app, ["ingest", "2402.11163", "--mode", "bogus"])
    assert bad.exit_code == 1
