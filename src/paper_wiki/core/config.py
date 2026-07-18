from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 包安装位置向上 3 层即仓库根目录（src/paper_wiki/core/config.py -> 项目根）。
_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_ROOT_ENV_FILE = str(_PACKAGE_ROOT / ".env")


def _has_project_markers(candidate: Path) -> bool:
    return (candidate / "raw").exists() and (candidate / "docs").exists()


def find_project_root(start: Path | None = None) -> Path:
    """从当前目录向上寻找项目根目录；根目录至少应包含 raw/ 和 docs/。

    若从 cwd 向上找不到（例如后端进程启动时的 cwd 与仓库不在同一棵目录树，
    如 systemd/pm2 等场景），回退到包安装位置推出的仓库根目录，避免静默用错路径。
    """
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if _has_project_markers(candidate):
            return candidate
    if _has_project_markers(_PACKAGE_ROOT):
        return _PACKAGE_ROOT
    return current


class Settings(BaseSettings):
    """全局配置入口，统一从 .env 和环境变量读取路径与模型配置。"""

    model_config = SettingsConfigDict(
        env_file=(_PACKAGE_ROOT_ENV_FILE, ".env"),
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
    wechat_appid: str | None = Field(default=None, validation_alias=AliasChoices("WECHAT_APPID"))
    wechat_secret: str | None = Field(default=None, validation_alias=AliasChoices("WECHAT_SECRET", "WECHAT_APPSECRET"))
    wechat_author: str | None = Field(default=None, validation_alias=AliasChoices("WECHAT_AUTHOR"))
    wechat_cover_path: Path | None = Field(default=None, validation_alias=AliasChoices("WECHAT_COVER_PATH"))
    wechat_thumb_media_id: str | None = Field(default=None, validation_alias=AliasChoices("WECHAT_THUMB_MEDIA_ID"))
    wechat_request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("WECHAT_REQUEST_TIMEOUT_SECONDS"),
    )
    cursor_headless_binary: str = Field(default="agent", validation_alias=AliasChoices("CURSOR_HEADLESS_BINARY"))
    cursor_headless_timeout_seconds: float = Field(
        default=300.0,
        validation_alias=AliasChoices("CURSOR_HEADLESS_TIMEOUT_SECONDS"),
    )
    cursor_render_theme: str = Field(default="摸鱼绿", validation_alias=AliasChoices("CURSOR_RENDER_THEME"))
    cursor_render_prompt_path: str = Field(
        default="blog_html_render_v1.py",
        validation_alias=AliasChoices("CURSOR_RENDER_PROMPT_PATH"),
    )
    arxiv_min_interval: float = Field(default=4.0, validation_alias=AliasChoices("ARXIV_MIN_INTERVAL"))
    search_max_results: int = Field(default=10, validation_alias=AliasChoices("SEARCH_MAX_RESULTS"))
    fetch_download_timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices("FETCH_DOWNLOAD_TIMEOUT_SECONDS"),
    )
    zotero_id: str | None = Field(default=None, validation_alias=AliasChoices("ZOTERO_ID"))
    zotero_key: str | None = Field(default=None, validation_alias=AliasChoices("ZOTERO_KEY"))
    zotero_library_type: str = Field(default="user", validation_alias=AliasChoices("ZOTERO_LIBRARY_TYPE"))
    zotero_ignore: str | None = Field(default=None, validation_alias=AliasChoices("ZOTERO_IGNORE"))
    arxiv_query: str = Field(default="cs.AI+cs.LG+cs.CL+cs.IR", validation_alias=AliasChoices("ARXIV_QUERY"))
    max_paper_num: int = Field(default=15, validation_alias=AliasChoices("MAX_PAPER_NUM"))
    recommend_candidate_pool_size: int = Field(
        default=200,
        validation_alias=AliasChoices("RECOMMEND_CANDIDATE_POOL_SIZE"),
    )
    recommend_embedding_model: str = Field(
        default="avsolatorio/GIST-small-Embedding-v0",
        validation_alias=AliasChoices("RECOMMEND_EMBEDDING_MODEL"),
    )
    max_llm_retries: int = 3
    request_timeout_seconds: float = 120.0
    max_parse_chars: int = 32000

    def resolved_raw_dir(self) -> Path:
        """返回 raw 目录的绝对路径，未显式配置时使用项目根目录下的 raw/。"""
        return (self.raw_dir or self.project_root / "raw").resolve()

    def resolved_artifacts_dir(self) -> Path:
        """返回 artifacts 目录的绝对路径，Layer1 assets 和语义产物会写入这里。"""
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
