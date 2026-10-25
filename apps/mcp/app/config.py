"""Configuration settings for FixProof MCP Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service Bindings
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    # Prometheus Integration
    PROMETHEUS_URL: str = "http://prometheus:9090"

    # Kubernetes Configuration
    KUBERNETES_NAMESPACE: str = "fixproof-demo"
    KUBERNETES_API_URL: str = "https://kubernetes.default.svc"
    KUBERNETES_TOKEN_PATH: str = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    KUBERNETES_CA_CERT_PATH: str = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    KUBECONFIG_PATH: str = ""

    # Direct Probe Target
    SAMPLE_APP_HEALTH_URL: str = "http://localhost:8080/healthz"

    # Capability Signing Key (shared with apps/api for one-use execution tokens)


settings = Settings()
