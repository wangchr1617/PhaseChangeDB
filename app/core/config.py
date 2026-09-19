from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取运行配置。"""

    app_name: str = "PhaseChangeDB"
    app_env: str = "development"
    database_url: str = "mysql+asyncmy://phasechange:phasechange@127.0.0.1:3306/phasechangedb"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    reviewer_token: str | None = None
    secret_key: str = "phasechange-dev-secret-key-change-in-production-32b"
    gemini_api_key: str | None = None
    deepseek_api_key: str | None = None
    crossref_mailto: str = "contact@phasechangedb.org"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PCM_", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
