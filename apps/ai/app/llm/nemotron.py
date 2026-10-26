"""Evidence-grounded analysis through the selected OpenAI-compatible provider."""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.llm.prompts import CAUSAL_REASONING_SYSTEM_PROMPT, CAUSAL_REASONING_USER_TEMPLATE
from app.schemas.state import EvidenceReference, Hypothesis


def live_model_config() -> tuple[str, str, str]:
    """Return model, key, and endpoint; fail closed on an unknown provider."""
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider == "groq":
        return settings.GROQ_MODEL, settings.GROQ_API_KEY, settings.GROQ_BASE_URL
    if provider == "nebius":
        return settings.NEBIUS_MODEL, settings.NEBIUS_API_KEY, settings.NEBIUS_BASE_URL
    raise RuntimeError(f"Unsupported live LLM provider: {provider}")


def live_model_available() -> bool:
    """Mock credentials never authorize an external model call."""
    try:
        _, key, _ = live_model_config()
    except RuntimeError:
        return False
    return bool(key and not key.startswith("mock"))


def get_nemotron_llm() -> ChatOpenAI:
    """Return the selected live provider using the existing client interface."""
    model, key, base_url = live_model_config()
    if not live_model_available():
        raise RuntimeError(f"{settings.LLM_PROVIDER} credentials are unavailable")
    return ChatOpenAI(
        model=model,
        api_key=key,
        base_url=base_url,
        temperature=0.1,
        max_tokens=2048,
        timeout=20,
        max_retries=1,
    )


async def generate_causal_analysis(
    incident_id: str,
    anomaly_id: str,
    namespace: str,
    deployment_name: str,
    evidence: list[EvidenceReference],
    mode: str = "live",
) -> tuple[list[Hypothesis], str]:
    """Execute causal reasoning over evidence snapshots using the selected model."""
    lines = []
    for ev in evidence:
        lines.append(
            f"- ID: {ev.id} | Source: {ev.source} | Hash: {ev.content_hash[:10]} | Fact: {ev.fact}"
        )
    evidence_block = "\n".join(lines) if lines else "No evidence collected."

    if mode == "synthetic":
        return _synthetic_causal_reasoning(evidence)
    if not live_model_available():
        raise RuntimeError(f"{settings.LLM_PROVIDER} credentials are unavailable for live investigation")

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


def _synthetic_causal_reasoning(evidence: list[EvidenceReference]) -> tuple[list[Hypothesis], str]:
    """Deterministic causal inference for local tests and offline dev."""
    ev_ids_by_source = {ev.source: ev.id for ev in evidence}
    metric_ev = ev_ids_by_source.get("prometheus")
    deploy_ev = ev_ids_by_source.get("kubernetes:deployment")
    log_ev = ev_ids_by_source.get("kubernetes:logs")

    hypotheses = []
    has_fail_mode = any(
        "FAIL_MODE" in ev.fact or "FAIL_MODE" in str(ev.raw_data)
        for ev in evidence
        if "deployment" in ev.source
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
                supporting_evidence_ids=[
                    eid for eid in [ev_ids_by_source.get("direct:probe")] if eid
                ],
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


def _parse_or_ground_hypotheses(
    response_text: str, evidence: list[EvidenceReference]
) -> tuple[list[Hypothesis], str]:
    """Extract hypotheses and ensure citations are present."""
    from app.guardrails.citations import CitationValidatorGuard

    extracted_ids = CitationValidatorGuard.extract_evidence_ids(response_text)
    valid_ids = {ev.id for ev in evidence}
    if not extracted_ids or not extracted_ids <= valid_ids:
        raise ValueError("Model response has missing or unknown evidence citations")
    matched_ids = sorted(extracted_ids)

    hypotheses = [
        Hypothesis(
            cause=response_text[:300].strip(),
            confidence=0.92,
            supporting_evidence_ids=matched_ids,
            is_root_cause=True,
        )
    ]
    summary = response_text[:200].strip()
    return hypotheses, summary
