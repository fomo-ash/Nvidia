from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+pysqlite:///./fixproof.db"
    llm_provider: Literal["mock"] = "mock"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    proposal_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
