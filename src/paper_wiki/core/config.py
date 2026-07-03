from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_project_root(start: Path | None = None) -> Path:
    """从当前目录向上寻找项目根目录；根目录至少应包含 raw/ 和 docs/。"""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "raw").exists() and (candidate / "docs").exists():
            return candidate
    return current


class Settings(BaseSettings):
    """全局配置入口，统一从 .env 和环境变量读取路径与模型配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_root: Path = Field(default_factory=find_project_root)
    raw_dir: Path | None = None
    artifacts_dir: Path | None = None
    prompts_dir: Path | None = None
    graph_state_dir: Path | None = None
    graph_updates_dir: Path | None = None

    # 兼容用户当前 .env 的 API_KEY/BASE_URL/MODEL_NAME，也兼容 OpenAI 官方命名。
    llm_provider: str = Field(default="openai", validation_alias=AliasChoices("LLM_PROVIDER", "PROVIDER"))
    model_name: str = Field(default="gpt-4o-mini", validation_alias=AliasChoices("MODEL_NAME", "OPENAI_MODEL"))
    base_url: str | None = Field(default=None, validation_alias=AliasChoices("BASE_URL", "OPENAI_BASE_URL"))
    api_key: str | None = Field(default=None, validation_alias=AliasChoices("API_KEY", "OPENAI_API_KEY"))
    neo4j_uri: str | None = Field(default=None, validation_alias=AliasChoices("NEO4J_URI"))
    neo4j_username: str | None = Field(default=None, validation_alias=AliasChoices("NEO4J_USERNAME", "NEO4J_USER"))
    neo4j_password: str | None = Field(default=None, validation_alias=AliasChoices("NEO4J_PASSWORD"))
    neo4j_database: str = Field(default="neo4j", validation_alias=AliasChoices("NEO4J_DATABASE"))
    max_llm_retries: int = 3
    request_timeout_seconds: float = 120.0
    max_parse_chars: int = 32000

    def resolved_raw_dir(self) -> Path:
        """返回 raw 目录的绝对路径，未显式配置时使用项目根目录下的 raw/。"""
        return (self.raw_dir or self.project_root / "raw").resolve()

    def resolved_artifacts_dir(self) -> Path:
        """返回 artifacts 目录的绝对路径，Layer1 三件套会写入这里。"""
        return (self.artifacts_dir or self.project_root / "artifacts").resolve()

    def resolved_prompts_dir(self) -> Path:
        """返回 prompts 目录的绝对路径，生成器从这里读取 prompt 模板。"""
        return (self.prompts_dir or self.project_root / "prompts").resolve()

    def resolved_graph_state_dir(self) -> Path:
        """返回 Layer2 图谱快照目录。"""
        return (self.graph_state_dir or self.project_root / "graph_state").resolve()

    def resolved_graph_updates_dir(self) -> Path:
        """返回 Layer2 图谱增量事件目录。"""
        return (self.graph_updates_dir or self.project_root / "graph_updates").resolve()


@lru_cache
def get_settings() -> Settings:
    """缓存 Settings，避免一次命令内重复解析 .env。"""
    return Settings()
