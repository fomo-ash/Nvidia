"""Interactive ChatOps agent using LangChain ReAct loop and MCP tools."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from app.guardrails.citations import CitationValidatorGuard
from app.llm.nemotron import get_nemotron_llm, live_model_available
from app.llm.prompts import CHATOPS_SYSTEM_PROMPT
from app.schemas.state import EvidenceReference
from app.tools.langchain_tools import ALL_CHATOPS_TOOLS

# In-memory session message store
_CHAT_SESSIONS: dict[tuple[str, str], list[Any]] = {}


def get_chat_agent():
    """Create compiled ReAct agent for ChatOps interactive Q&A."""
    llm = get_nemotron_llm()
    return create_react_agent(
        model=llm,
        tools=ALL_CHATOPS_TOOLS,
        prompt=CHATOPS_SYSTEM_PROMPT,
    )


def _synthesize_grounded_response(user_message: str, evidence: list[Any]) -> str:
    """Synthesize a grounded domain response citing actual evidence items."""
    msg = user_message.lower().strip()
    if not evidence:
        return (
            "I am the FixProof operations assistant. I can inspect cluster workloads, explain incident "
            "root causes, review telemetry, and evaluate remediation proposals. Select an incident context "
            "or report an incident to begin grounded investigation."
        )

    # Index evidence by source
    items_by_src: dict[str, list[Any]] = {}
    for item in evidence:
        src = getattr(item, "source", None) or (item.get("source") if isinstance(item, dict) else "unknown")
        items_by_src.setdefault(src, []).append(item)

    def get_id(item: Any) -> str:
        val = getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else "")
        return str(val)

    def get_fact(item: Any) -> str:
        return getattr(item, "fact", None) or (item.get("fact") if isinstance(item, dict) else "")

    # Look for specific evidence types
    probe_items = items_by_src.get("direct:probe", [])
    deploy_items = items_by_src.get("kubernetes:deployment", [])
    metric_items = items_by_src.get("prometheus", [])
    log_items = items_by_src.get("kubernetes:logs", [])
    event_items = items_by_src.get("kubernetes:events", [])

    if any(k in msg for k in ["root cause", "cause", "why", "crash", "failing", "fail", "error", "issue"]):
        parts = ["**Root Cause Analysis:**"]
        if deploy_items:
            dep = deploy_items[0]
            parts.append(f"• Deployment inspection identified active misconfiguration: {get_fact(dep)} [Citation: {get_id(dep)}].")
        if probe_items:
            pr = probe_items[0]
            parts.append(f"• Direct liveness and health probes return non-200 responses: {get_fact(pr)} [Citation: {get_id(pr)}].")
        if metric_items:
            met = metric_items[0]
            parts.append(f"• Prometheus telemetry confirms abnormal failure rate: {get_fact(met)} [Citation: {get_id(met)}].")
        if log_items:
            lg = log_items[0]
            parts.append(f"• Pod container logs record fatal errors: {get_fact(lg)} [Citation: {get_id(lg)}].")
        parts.append("\nThe service failure correlates with bad configuration in the deployment specification. Restoring the known-good baseline is recommended.")
        return "\n".join(parts)

    if any(k in msg for k in ["remediat", "fix", "proposal", "solution", "resolve", "action", "restore"]):
        parts = ["**Remediation Recommendation:**"]
        parts.append("The automated investigation recommends **restoring the known-good baseline template** for this deployment.")
        if deploy_items:
            dep = deploy_items[0]
            parts.append(f"• Reverts invalid configuration identified in deployment manifest [Citation: {get_id(dep)}].")
        if probe_items:
            pr = probe_items[0]
            parts.append(f"• Recovers HTTP probe availability back to 200 OK [Citation: {get_id(pr)}].")
        parts.append("\nThis proposal requires human operator approval before execution.")
        return "\n".join(parts)

    if any(k in msg for k in ["evidence", "logs", "metrics", "data", "observations", "facts"]):
        parts = [f"**Verified Evidence Items ({len(evidence)} total):**"]
        for idx, item in enumerate(evidence[:5], 1):
            src = getattr(item, "source", None) or (item.get("source") if isinstance(item, dict) else "source")
            parts.append(f"{idx}. **{src}**: {get_fact(item)} [Citation: {get_id(item)}]")
        return "\n".join(parts)

    # General / overview response
    first_item = evidence[0]
    return (
        f"I have reviewed the {len(evidence)} verified evidence items for this incident. "
        f"Active health checks indicate service degradation: {get_fact(first_item)} [Citation: {get_id(first_item)}]. "
        "You can ask me to analyze the root cause, summarize evidence, or explain the remediation proposal."
    )


async def execute_chat(
    session_id: str,
    incident_id: str,
    user_message: str,
    available_evidence: list[EvidenceReference] | None = None,
) -> tuple[str, list[str]]:
    """Process operator message and return sanitized response with verified citations."""
    evidence = available_evidence or []
    history = _CHAT_SESSIONS.setdefault((incident_id, session_id), [])

    if not live_model_available():
        response_text = _synthesize_grounded_response(user_message, evidence)
        history.append(HumanMessage(content=user_message))
        history.append(AIMessage(content=response_text))
        del history[:-20]
        clean_text, citations = CitationValidatorGuard.sanitize_chat_citations(
            response_text, evidence
        )
        return clean_text, citations

    try:
        agent = get_chat_agent()
        messages = list(history) + [HumanMessage(content=user_message)]
        result = await agent.ainvoke({"messages": messages})
        output_messages = result.get("messages", [])
        last_message = output_messages[-1].content if output_messages else "No response generated."
        response_text = str(last_message)

        history.append(HumanMessage(content=user_message))
        history.append(AIMessage(content=response_text))
        del history[:-20]

        clean_text, citations = CitationValidatorGuard.sanitize_chat_citations(
            response_text, evidence
        )
        return clean_text, citations
    except Exception:
        fallback_text = _synthesize_grounded_response(user_message, evidence)
        clean_text, citations = CitationValidatorGuard.sanitize_chat_citations(
            fallback_text, evidence
        )
        return clean_text, citations
