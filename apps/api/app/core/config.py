from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+pysqlite:///./fixproof.db"
    llm_provider: Literal["mock"] = "mock"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    proposal_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    local_demo_enabled: bool = True
    operator_secret: str = ""
    session_signing_key: str = ""
    sample_target_uid: str = ""
    sample_cluster_id: str = "local-kind"
    mcp_server_url: str = "http://mcp:8002"
    ai_service_url: str = "http://ai:8001"
    service_auth_token: str = ""
    investigation_lease_seconds: int = Field(default=180, ge=120, le=3600)
    analysis_enabled: bool = False
    live_execution_enabled: bool = False
    execution_signing_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
