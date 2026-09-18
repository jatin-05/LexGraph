from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Contract Intelligence API"
    environment: str = "development"

    supabase_url: str
    supabase_secret_key: str

    # Local Ollama model used by Docling Graph.
    graph_model: str = "qwen3:1.7b"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


# from functools import lru_cache

# from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#     app_name: str = "Contract Intelligence API"
#     environment: str = "development"

#     supabase_url: str
#     supabase_secret_key: str

#     model_config = SettingsConfigDict(
#         env_file=".env",
#         env_file_encoding="utf-8",
#         extra="ignore",
#     )


# @lru_cache
# def get_settings() -> Settings:
#     return Settings()