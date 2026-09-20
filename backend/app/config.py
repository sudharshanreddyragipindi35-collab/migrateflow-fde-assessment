from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./migrateflow.db"
    upload_root: str = "./uploads"
    max_upload_files: int = 10
    max_upload_bytes: int = 10 * 1024 * 1024
    max_source_rows: int = 50000
    max_source_columns: int = 100
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    llm_request_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_parallel_workers: int = Field(default=3, ge=1, le=16)
    llm_failover_provider: str = "fallback"
    model_mode: str = "ollama"
    mapping_fast_path: bool = True
    mock_target_base_url: str = ""
    demo_failures: bool = False
    cors_origins: str = "http://localhost:5173"
    max_model_prompt_chars: int = 12000
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    auto_create_schema: bool = True

    model_config = SettingsConfigDict(
        env_file=(str(Path(__file__).resolve().parents[2] / ".env"), ".env"), extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
