"""Interactive ChatOps agent using LangChain ReAct loop and MCP tools."""

from typing import Any
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.guardrails.citations import CitationValidatorGuard
from app.llm.nemotron import get_nemotron_llm
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


async def execute_chat(
    session_id: str,
    incident_id: str,
    user_message: str,
    available_evidence: list[EvidenceReference] | None = None,
) -> tuple[str, list[str]]:
    """Process operator message and return sanitized response with verified citations."""
    evidence = available_evidence or []
    history = _CHAT_SESSIONS.setdefault((incident_id, session_id), [])

    if settings.NEBIUS_API_KEY.startswith("mock") or not settings.NEBIUS_API_KEY:
        response_text = "Live model analysis is unavailable. Review the collected evidence manually."
        history.append(HumanMessage(content=user_message))
        history.append(AIMessage(content=response_text))
        del history[:-20]
        clean_text, citations = CitationValidatorGuard.sanitize_chat_citations(response_text, evidence)
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

        clean_text, citations = CitationValidatorGuard.sanitize_chat_citations(response_text, evidence)
        return clean_text, citations
    except Exception:
        fallback_text = "Model analysis is unavailable. Review the collected evidence manually."
        clean_text, citations = CitationValidatorGuard.sanitize_chat_citations(fallback_text, evidence)
        return clean_text, citations
