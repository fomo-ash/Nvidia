"""Configuration settings for FixProof AI Agent Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service Bindings
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Select the live model explicitly. Synthetic mode is selected per request.
    LLM_PROVIDER: str = "nebius"

    # Groq OpenAI-compatible API (temporary live provider)
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # Nebius Token Factory / NVIDIA Nemotron 70B
    NEBIUS_API_KEY: str = "mock-nebius-key"
    NEBIUS_BASE_URL: str = "https://api.studio.nebius.ai/v1"
    NEBIUS_MODEL: str = "nvidia/llama-3.1-nemotron-70b-instruct"

    # TypeSafe Jev System-1 Decisions (Official: https://api.typesafe.ai/ & https://jevtypesafeai.com/jev/api)
    TYPESAFE_API_KEY: str = "mock-typesafe-key"
    JEV_API_KEY: str = ""
    TYPESAFE_BASE_URL: str = "https://api.typesafe.ai"

    @property
    def EFFECTIVE_JEV_KEY(self) -> str:
        return self.JEV_API_KEY if self.JEV_API_KEY else self.TYPESAFE_API_KEY

    # PostgreSQL Database for Checkpointing and Audit
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/fixproof"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@postgres:5432/fixproof"

    # Upstream Services
    MCP_SERVER_URL: str = "http://mcp:8002"
    API_BASE_URL: str = "http://api:8000"


settings = Settings()
