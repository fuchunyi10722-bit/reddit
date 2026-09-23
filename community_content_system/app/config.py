"""应用配置。

生产环境部署到能联网 Reddit 的服务器时,改 DATABASE_URL 为 PostgreSQL+pgvector,
设置 adapter=reddit 并提供 RedditCredentials。沙箱开发期默认 adapter=file。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings


class AdapterType(str, Enum):
    FILE = "file"
    REDDIT = "reddit"
    MANUAL = "manual"
    EXCEL = "excel"


class Settings(BaseSettings):
    # 数据库:沙箱用 SQLite;生产切 postgresql+psycopg://...@/community
    database_url: str = "sqlite:///./community.db"

    # 数据获取层选择
    adapter: AdapterType = AdapterType.FILE
    fixtures_root: str = "fixtures"

    # RedditAdapter 生产凭据(沙箱期留空)
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    reddit_password: str = ""
    reddit_user_agent: str = "platform:community-content-system:v0.1 (by /u/placeholder)"

    # LLM Provider 配置
    # 沙箱无 Ollama 也无付费凭据时用 mock(确定性规则输出,验证链路)
    # 部署到有 Ollama 的机器:llm_provider=ollama
    # 接付费 API:llm_provider=openai_compatible + base_url + api_key
    llm_provider: str = "mock"  # mock | ollama | openai_compatible
    llm_classifier_model: str = "qwen2.5:7b"          # Classifier 用轻量本地模型
    llm_analyzer_model: str = "qwen2.5:14b"          # ContentAnalyzer 用较强本地模型
    llm_api_base: str = "http://localhost:11434"     # Ollama 默认地址
    llm_api_key: str = ""                            # 付费 provider 用
    llm_timeout: int = 120
    llm_retries: int = 2
    llm_temperature: float = 0.3
    llm_prompt_version: str = "v2.1"

    # Embedding 配置
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # 社区初始化默认 budget(可被调用方覆盖)
    init_top_limit: int = 100
    init_hot_limit: int = 50
    init_new_limit: int = 100
    init_search_limit: int = 20
    init_search_query_count: int = 3
    comment_deep_fetch_total: int = 90
    tier_allocation_high: float = 0.4
    tier_allocation_mid: float = 0.4
    tier_allocation_low: float = 0.2
    per_post_comment_limit: int = 20
    per_post_comment_sort: str = "top"
    sample_max_per_author: int = 2
    sample_title_similarity_threshold: float = 0.9
    sample_time_bucket_hours: int = 6
    sample_max_per_bucket: int = 5

    # KnowledgePattern 状态迁移阈值
    pattern_promote_threshold: int = 3   # confirmed >= 此值且 contradicted=0 → supported
    pattern_refute_threshold: int = 3    # contradicted >= 此值且 confirmed=0 → refuted

    class Config:
        env_prefix = "CCS_"
        env_file = ".env"


settings = Settings()
