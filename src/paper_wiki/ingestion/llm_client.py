from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import TypeVar

import httpx
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from paper_wiki.core.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """LLM 调用抽象层，便于后续切换不同 OpenAI-compatible 服务。"""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError

    def complete_json(self, system: str, user: str, schema: type[T]) -> T:
        """要求模型返回 JSON，并用 Pydantic schema 做强校验和有限重试。"""
        last_error: Exception | None = None
        for attempt in range(1, get_settings().max_llm_retries + 1):
            # 第二次开始把错误反馈给模型，让它只修 JSON 结构，不重新发挥。
            logger.debug("开始请求 JSON 输出：schema=%s, attempt=%d", schema.__name__, attempt)
            suffix = "" if attempt == 1 else f"\n\nReturn corrected valid JSON only. Previous error: {last_error}"
            text = self.complete(system, user + suffix)
            try:
                result = schema.model_validate(self._extract_json(text))
                logger.debug("JSON 输出校验通过：schema=%s, attempt=%d", schema.__name__, attempt)
                return result
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning("JSON 输出校验失败：schema=%s, attempt=%d, error=%s", schema.__name__, attempt, exc)
        logger.error("JSON 输出重试后仍失败：schema=%s, error=%s", schema.__name__, last_error)
        raise ValueError(f"LLM did not return valid {schema.__name__}: {last_error}") from last_error

    def _extract_json(self, text: str) -> object:
        """从模型回复中提取 JSON，兼容 ```json fence 和前后解释性文字。"""
        cleaned = text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            cleaned = fence.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start_candidates = [idx for idx in [cleaned.find("{"), cleaned.find("[")] if idx >= 0]
            if not start_candidates:
                raise
            start = min(start_candidates)
            end = max(cleaned.rfind("}"), cleaned.rfind("]"))
            if end <= start:
                raise
            return json.loads(cleaned[start : end + 1])


class OpenAIClient(LLMClient):
    """OpenAI SDK 客户端；通过 base_url 支持 DeepSeek 等兼容接口。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.api_key:
            logger.error("缺少 API_KEY/OPENAI_API_KEY，无法构造 LLM 客户端")
            raise ValueError("Missing API_KEY/OPENAI_API_KEY in environment")
        kwargs = {
            "api_key": self.settings.api_key,
            "http_client": httpx.Client(
                timeout=self.settings.request_timeout_seconds,
                trust_env=False,
            ),
        }
        if self.settings.base_url:
            kwargs["base_url"] = self.settings.base_url
        self.client = OpenAI(**kwargs)
        logger.debug(
            "OpenAI-compatible 客户端初始化完成：provider=%s, model=%s, proxy=disabled",
            self.settings.llm_provider,
            self.settings.model_name,
        )

    def complete(self, system: str, user: str) -> str:
        """执行一次 chat completion，返回纯文本内容。"""
        logger.info("开始调用 LLM：model=%s", self.settings.model_name)
        response = self.client.chat.completions.create(
            model=self.settings.model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        if not content:
            logger.error("LLM 返回空内容：model=%s", self.settings.model_name)
            raise ValueError("LLM returned empty content")
        logger.info("LLM 调用完成：model=%s, chars=%d", self.settings.model_name, len(content))
        return content


def build_llm_client(settings: Settings | None = None) -> LLMClient:
    """根据配置构造 LLM client；当前只开放 OpenAI-compatible 路线。"""
    settings = settings or get_settings()
    if settings.llm_provider.lower() in {"openai", "deepseek"}:
        logger.debug("选择 OpenAI-compatible LLM provider：%s", settings.llm_provider)
        return OpenAIClient(settings)
    logger.error("不支持的 LLM_PROVIDER：%s", settings.llm_provider)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
