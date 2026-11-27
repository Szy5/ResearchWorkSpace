"""LangSmith (LangChain Agent Lake) tracing helpers.

Keeps tracing strictly opt-in via ``Settings.langsmith_tracing`` and
``Settings.langsmith_api_key``, so unit tests and offline runs never leak
network traffic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import logging
from typing import Any, TypeVar

from langsmith import Client, get_current_run_tree, tracing_context
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from paper_wiki.core.config import Settings

logger = logging.getLogger(__name__)

TClient = TypeVar("TClient")


def is_tracing_enabled(settings: Settings) -> bool:
    """Return True only when tracing is explicitly enabled and an API key is present."""
    return bool(settings.langsmith_tracing and settings.langsmith_api_key)


def build_langsmith_client(settings: Settings) -> Client | None:
    """Construct a LangSmith Client when tracing is enabled, else None."""
    if not is_tracing_enabled(settings):
        return None
    kwargs: dict[str, Any] = {"api_key": settings.langsmith_api_key}
    if settings.langsmith_endpoint:
        kwargs["api_url"] = settings.langsmith_endpoint
    return Client(**kwargs)


def maybe_wrap_openai(client: TClient, settings: Settings) -> TClient:
    """Wrap an OpenAI client with LangSmith auto-tracing when enabled."""
    if not is_tracing_enabled(settings) or not isinstance(client, OpenAI):
        return client
    return wrap_openai(client)


def current_trace_id() -> str | None:
    """Return the active LangSmith root trace/run ID if currently inside a traced run."""
    run_tree = get_current_run_tree()
    if run_tree is None:
        return None
    return str(run_tree.trace_id or run_tree.id)


@contextmanager
def langsmith_trace_scope(
    settings: Settings,
    *,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Client | None]:
    """Enter an isolated LangSmith tracing context and flush traces on exit."""
    ls_client = build_langsmith_client(settings)
    if ls_client is None:
        with tracing_context(enabled=False):
            yield None
        return

    with tracing_context(
        enabled=True,
        project_name=settings.langsmith_project,
        tags=tags,
        metadata=metadata,
        client=ls_client,
    ):
        try:
            yield ls_client
        finally:
            try:
                ls_client.flush()
            except Exception as exc:  # flushing observability must not fail paper ingestion
                logger.warning("LangSmith 轨迹 flush 失败（不影响产物写入）：%s", exc)
