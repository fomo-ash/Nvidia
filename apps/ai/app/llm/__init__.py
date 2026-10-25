"""LLM integration package for NVIDIA Nemotron 70B."""

from app.llm.nemotron import generate_causal_analysis, get_nemotron_llm
from app.llm.prompts import CAUSAL_REASONING_SYSTEM_PROMPT, CHATOPS_SYSTEM_PROMPT

__all__ = [
    "get_nemotron_llm",
    "generate_causal_analysis",
    "CAUSAL_REASONING_SYSTEM_PROMPT",
    "CHATOPS_SYSTEM_PROMPT",
]
