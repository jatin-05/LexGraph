from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Contract Intelligence API"
    environment: str = "development"

    supabase_url: str
    supabase_secret_key: str

    graph_model: str = "qwen2.5:3b-instruct"
    extraction_model: str = "qwen2.5:3b"
    ollama_base_url: str = "http://localhost:11434/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()