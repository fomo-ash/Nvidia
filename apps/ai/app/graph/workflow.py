"""LangGraph StateGraph assembly and checkpointer compilation."""

from typing import Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.nodes import (
    collect_telemetry_node,
    evaluate_sufficiency_node,
    reason_causes_node,
    score_risk_node,
    synthesize_proposal_node,
)
from app.graph.routing import route_after_sufficiency
from app.schemas.state import InvestigationState


def build_investigation_graph(checkpointer: Any = None) -> Any:
    """Build and compile the LangGraph incident investigation workflow."""
    builder = StateGraph(InvestigationState)

    builder.add_node("collect_telemetry", collect_telemetry_node)
    builder.add_node("evaluate_sufficiency", evaluate_sufficiency_node)
    builder.add_node("reason_causes", reason_causes_node)
    builder.add_node("score_risk", score_risk_node)
    builder.add_node("synthesize_proposal", synthesize_proposal_node)
    builder.add_node(
        "needs_review",
        lambda state: {
            "investigation_status": "needs_review",
            "remediation_proposal": None,
            "root_cause_summary": state.get("root_cause_summary")
            or "Insufficient live evidence; manual review required.",
        },
    )

    builder.add_edge(START, "collect_telemetry")
    builder.add_edge("collect_telemetry", "evaluate_sufficiency")

    builder.add_conditional_edges(
        "evaluate_sufficiency",
        route_after_sufficiency,
        {
            "collect_telemetry": "collect_telemetry",
            "reason_causes": "reason_causes",
            "needs_review": "needs_review",
        },
    )

    builder.add_conditional_edges(
        "reason_causes",
        lambda state: "needs_review"
        if state.get("investigation_status") == "needs_review"
        else "score_risk",
        {"needs_review": "needs_review", "score_risk": "score_risk"},
    )
    builder.add_edge("score_risk", "synthesize_proposal")
    builder.add_edge("synthesize_proposal", END)
    builder.add_edge("needs_review", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)


investigation_workflow = build_investigation_graph()
