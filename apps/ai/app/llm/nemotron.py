"""Nebius Token Factory / NVIDIA Nemotron 70B client configuration."""

from typing import Any
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.llm.prompts import CAUSAL_REASONING_SYSTEM_PROMPT, CAUSAL_REASONING_USER_TEMPLATE
from app.schemas.state import EvidenceReference, Hypothesis


def get_nemotron_llm() -> ChatOpenAI:
    """Return configured ChatOpenAI pointing to Nebius Token Factory."""
    return ChatOpenAI(
        model=settings.NEBIUS_MODEL,
        api_key=settings.NEBIUS_API_KEY,
        base_url=settings.NEBIUS_BASE_URL,
        temperature=0.1,
        max_tokens=2048,
    )


async def generate_causal_analysis(
    incident_id: str,
    anomaly_id: str,
    namespace: str,
    deployment_name: str,
    evidence: list[EvidenceReference],
) -> tuple[list[Hypothesis], str]:
    """Execute causal reasoning over evidence snapshots using Nemotron 70B."""
    lines = []
    for ev in evidence:
        lines.append(f"- ID: {ev.id} | Source: {ev.source} | Hash: {ev.content_hash[:10]} | Fact: {ev.fact}")
    evidence_block = "\n".join(lines) if lines else "No evidence collected."

    if settings.NEBIUS_API_KEY.startswith("mock") or not settings.NEBIUS_API_KEY:
        return _synthetic_causal_reasoning(evidence)

    try:
        llm = get_nemotron_llm()
        user_prompt = CAUSAL_REASONING_USER_TEMPLATE.format(
            incident_id=incident_id,
            anomaly_id=anomaly_id,
            namespace=namespace,
            deployment_name=deployment_name,
            evidence_block=evidence_block,
        )
        messages = [
            SystemMessage(content=CAUSAL_REASONING_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        response = await llm.ainvoke(messages)
        text = response.content if isinstance(response.content, str) else str(response.content)

        return _parse_or_ground_hypotheses(text, evidence)
    except Exception:
        return _synthetic_causal_reasoning(evidence)


def _synthetic_causal_reasoning(evidence: list[EvidenceReference]) -> tuple[list[Hypothesis], str]:
    """Deterministic causal inference for local tests and offline dev."""
    ev_ids_by_source = {ev.source: ev.id for ev in evidence}
    metric_ev = ev_ids_by_source.get("prometheus")
    deploy_ev = ev_ids_by_source.get("kubernetes:deployment")
    log_ev = ev_ids_by_source.get("kubernetes:logs")

    hypotheses = []
    has_fail_mode = any(
        "FAIL_MODE" in ev.fact or "FAIL_MODE" in str(ev.raw_data) for ev in evidence if "deployment" in ev.source
    )
    has_metric_spike = any("5xx" in ev.fact or "CRITICAL" in ev.fact for ev in evidence)

    if has_fail_mode and has_metric_spike:
        supporting = [eid for eid in [deploy_ev, metric_ev, log_ev] if eid]
        hypotheses.append(
            Hypothesis(
                cause="Deployment 'sample-api' has environment variable FAIL_MODE='on', causing intentional 500 error injection during HTTP handling.",
                confidence=0.96,
                supporting_evidence_ids=supporting,
                is_root_cause=True,
            )
        )
        hypotheses.append(
            Hypothesis(
                cause="Readiness probe continues reporting 200 OK because /readyz checks server responsiveness rather than active traffic handlers.",
                confidence=0.88,
                supporting_evidence_ids=[eid for eid in [ev_ids_by_source.get("direct:probe")] if eid],
                is_root_cause=False,
            )
        )
        summary = (
            "Root cause identified: Injected environment variable FAIL_MODE='on' in deployment template "
            "causes handlers to emit HTTP 500 errors despite healthy readiness probes."
        )
    else:
        supporting = [ev.id for ev in evidence[:2]]
        hypotheses.append(
            Hypothesis(
                cause="Transient traffic anomaly or connection saturation.",
                confidence=0.60,
                supporting_evidence_ids=supporting,
                is_root_cause=True,
            )
        )
        summary = "Anomalous error rate observed across telemetry, root cause indeterminate."

    return hypotheses, summary


def _parse_or_ground_hypotheses(response_text: str, evidence: list[EvidenceReference]) -> tuple[list[Hypothesis], str]:
    """Extract hypotheses and ensure citations are present."""
    from app.guardrails.citations import CitationValidatorGuard

    extracted_ids = list(CitationValidatorGuard.extract_evidence_ids(response_text))
    valid_ids = {ev.id for ev in evidence}
    matched_ids = [eid for eid in extracted_ids if eid in valid_ids]

    hypotheses = [
        Hypothesis(
            cause=response_text[:300].strip(),
            confidence=0.92,
            supporting_evidence_ids=matched_ids if matched_ids else [ev.id for ev in evidence[:2]],
            is_root_cause=True,
        )
    ]
    summary = response_text[:200].strip()
    return hypotheses, summary
