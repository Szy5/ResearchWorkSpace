"""Minimal OpenAI-compatible Agent Loop with LangSmith Agent Lake tracing."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from langsmith import traceable
from openai import OpenAI
from pydantic import BaseModel, Field

from paper_wiki.core.config import Settings, get_settings
from paper_wiki.ingestion.agent.sandbox import PaperSandbox, TOOL_SCHEMAS
from paper_wiki.ingestion.agent.tracing import current_trace_id, langsmith_trace_scope, maybe_wrap_openai

logger = logging.getLogger(__name__)


class AgentUsage(BaseModel):
    """Aggregated token and call counts across one Agent Loop run."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0


class ToolCallRecord(BaseModel):
    """Lightweight audit record of one tool execution inside the loop."""

    step: int
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    output_chars: int = 0


class AgentRunResult(BaseModel):
    """Final output and observability metadata from one Agent Loop execution."""

    content: str
    steps: int
    usage: AgentUsage = Field(default_factory=AgentUsage)
    trace_id: str | None = None
    tool_history: list[ToolCallRecord] = Field(default_factory=list)


@traceable(run_type="tool", name="paper_sandbox_tool")
def _execute_sandbox_tool(sandbox: PaperSandbox, name: str, arguments: dict[str, Any]) -> str:
    """Execute one read-only sandbox tool inside a dedicated LangSmith tool span."""
    return sandbox.dispatch(name, arguments)


def _extract_cached_tokens(usage: Any) -> int:
    """Extract cached prompt tokens across OpenAI/Gemini and DeepSeek response shapes."""
    if usage is None:
        return 0
    direct = getattr(usage, "prompt_cache_hit_tokens", None)
    if isinstance(direct, int):
        return direct
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", None)
        if isinstance(cached, int):
            return cached
        if isinstance(details, dict) and isinstance(details.get("cached_tokens"), int):
            return details["cached_tokens"]
    if isinstance(usage, dict):
        if isinstance(usage.get("prompt_cache_hit_tokens"), int):
            return usage["prompt_cache_hit_tokens"]
        nested = usage.get("prompt_tokens_details") or {}
        if isinstance(nested.get("cached_tokens"), int):
            return nested["cached_tokens"]
    return 0


def _accumulate_usage(target: AgentUsage, response: Any) -> None:
    usage = getattr(response, "usage", None)
    target.llm_calls += 1
    if usage is None:
        return
    prompt = getattr(usage, "prompt_tokens", None) or 0
    completion = getattr(usage, "completion_tokens", None) or 0
    total = getattr(usage, "total_tokens", None) or (prompt + completion)
    target.prompt_tokens += int(prompt)
    target.completion_tokens += int(completion)
    target.total_tokens += int(total)
    target.cached_tokens += _extract_cached_tokens(usage)


def _serialize_assistant_message(message: Any) -> dict[str, Any]:
    """Keep only standard OpenAI assistant fields for maximum proxy compatibility."""
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": getattr(message, "content", None) or "",
    }
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = [
            {
                "id": tc.id,
                "type": getattr(tc, "type", "function") or "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in tool_calls
        ]
    return payload


def _build_openai_client(settings: Settings) -> OpenAI:
    if not settings.api_key:
        raise ValueError("Missing API_KEY/OPENAI_API_KEY in environment")
    timeout = httpx.Timeout(
        connect=settings.llm_connect_timeout_seconds,
        read=settings.request_timeout_seconds,
        write=settings.request_timeout_seconds,
        pool=settings.llm_connect_timeout_seconds,
    )
    http_client_kwargs: dict[str, Any] = {"timeout": timeout}
    if settings.llm_http_proxy:
        http_client_kwargs["proxy"] = settings.llm_http_proxy
        http_client_kwargs["trust_env"] = False
    else:
        http_client_kwargs["trust_env"] = True

    kwargs: dict[str, Any] = {
        "api_key": settings.api_key,
        "http_client": httpx.Client(**http_client_kwargs),
        "max_retries": 1,
    }
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    return OpenAI(**kwargs)


class PaperAgentLoop:
    """Append-only tool-calling loop for exploring a single paper folder."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
        max_steps: int | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.max_steps = max(2, max_steps or self.settings.agent_max_steps)
        raw_client = client if client is not None else _build_openai_client(self.settings)
        self.client = maybe_wrap_openai(raw_client, self.settings)

    def run(
        self,
        *,
        slug: str,
        system_prompt: str,
        initial_user_prompt: str,
        sandbox: PaperSandbox,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRunResult:
        """Run the agent loop inside a LangSmith tracing scope and return result + stats."""
        run_tags = ["paper-wiki", "paper-agent", self.settings.model_name, *(tags or [])]
        run_metadata = {
            "slug": slug,
            "model": self.settings.model_name,
            "max_steps": self.max_steps,
            **(metadata or {}),
        }
        with langsmith_trace_scope(self.settings, tags=run_tags, metadata=run_metadata):
            return self._run_traced(
                slug=slug,
                system_prompt=system_prompt,
                initial_user_prompt=initial_user_prompt,
                sandbox=sandbox,
            )

    @traceable(run_type="chain", name="paper_reader_agent")
    def _run_traced(
        self,
        *,
        slug: str,
        system_prompt: str,
        initial_user_prompt: str,
        sandbox: PaperSandbox,
    ) -> AgentRunResult:
        # Append-only messages preserve prefix prompt caching across loop iterations.
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_user_prompt},
        ]
        usage = AgentUsage()
        tool_history: list[ToolCallRecord] = []

        for step in range(1, self.max_steps + 1):
            is_last_step = step == self.max_steps
            if is_last_step and messages[-1]["role"] == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": "你已达到最大检索步数，请立即基于已读取的材料直接输出最终完整的中文精读 Markdown（不要再调用工具）。",
                    }
                )

            request_kwargs: dict[str, Any] = {
                "model": self.settings.model_name,
                "messages": messages,
                "temperature": 0.1,
            }
            if not is_last_step:
                request_kwargs["tools"] = TOOL_SCHEMAS
                request_kwargs["tool_choice"] = "auto"

            logger.info("Agent Loop 第 %d/%d 步：slug=%s, model=%s", step, self.max_steps, slug, self.settings.model_name)
            response = self.client.chat.completions.create(**request_kwargs)
            _accumulate_usage(usage, response)

            message = response.choices[0].message
            messages.append(_serialize_assistant_message(message))
            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls or is_last_step:
                content = (getattr(message, "content", None) or "").strip()
                if not content:
                    raise ValueError(f"Agent returned empty final content on step {step} for slug={slug}")
                trace_id = current_trace_id()
                logger.info(
                    "Agent Loop 完成：slug=%s, steps=%d, tool_calls=%d, prompt_tokens=%d, cached_tokens=%d, completion_tokens=%d, trace_id=%s",
                    slug,
                    step,
                    usage.tool_calls,
                    usage.prompt_tokens,
                    usage.cached_tokens,
                    usage.completion_tokens,
                    trace_id,
                )
                return AgentRunResult(
                    content=content,
                    steps=step,
                    usage=usage,
                    trace_id=trace_id,
                    tool_history=tool_history,
                )

            for tc in tool_calls:
                tool_name = tc.function.name
                raw_args = tc.function.arguments or "{}"
                try:
                    parsed_args = json.loads(raw_args)
                    if not isinstance(parsed_args, dict):
                        raise ValueError("Tool arguments must be a JSON object.")
                except (json.JSONDecodeError, ValueError) as exc:
                    tool_output = f"Error: Invalid JSON arguments for {tool_name}: {exc}"
                    parsed_args = {}
                else:
                    tool_output = _execute_sandbox_tool(sandbox, tool_name, parsed_args)

                usage.tool_calls += 1
                tool_history.append(
                    ToolCallRecord(
                        step=step,
                        name=tool_name,
                        arguments=parsed_args,
                        output_chars=len(tool_output),
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_output,
                    }
                )

        raise RuntimeError(f"Agent Loop exited unexpectedly without output for slug={slug}")
