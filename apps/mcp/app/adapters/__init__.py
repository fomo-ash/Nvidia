"""Adapters package for FixProof MCP Server."""

from app.adapters.kubernetes import KubernetesClient
from app.adapters.probe import ProbeClient
from app.adapters.prometheus import PrometheusClient

__all__ = ["PrometheusClient", "KubernetesClient", "ProbeClient"]
