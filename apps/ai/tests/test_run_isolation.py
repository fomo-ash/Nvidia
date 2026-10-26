"""Fresh runs of one incident must collect independently."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import main
from app.graph import nodes
from app.graph.workflow import build_investigation_graph
from app.schemas.api import ChatRequest, InvestigationRequest
from app.schemas.state import EvidenceReference


@pytest.mark.asyncio
async def test_reinvestigation_does_not_reuse_evidence(monkeypatch):
    graph = build_investigation_graph()
    monkeypatch.setattr(main, "investigation_workflow", graph)
    monkeypatch.setattr(nodes.jev, "api_key", "mock")
    calls = []

    def collector(source):
        async def collect(*args, **kwargs):
            calls.append(source)
            return EvidenceReference(
                id=f"EVD-{uuid4().hex[:8]}",
                observed_at=datetime.now(timezone.utc),
                content_hash="a" * 64,
                source=source,
                fact="fresh observation",
            )

        return collect

    for method, source in [
        ("query_metrics", "prometheus"),
        ("get_deployment_status", "kubernetes:deployment"),
        ("get_pod_logs", "kubernetes:logs"),
        ("get_pod_events", "kubernetes:events"),
        ("check_service_health", "direct:probe"),
    ]:
        monkeypatch.setattr(nodes.mcp, method, collector(source))
    first = await main.investigate_incident(
        InvestigationRequest(incident_id="same", anomaly_id="one", mode="synthetic")
    )
    second = await main.investigate_incident(
        InvestigationRequest(incident_id="same", anomaly_id="two", mode="synthetic")
    )
    assert first.investigation_id != second.investigation_id
    assert len(calls) == 10
    assert first.evidence_count == second.evidence_count == 5
    assert {ev.id for ev in first.evidence}.isdisjoint(ev.id for ev in second.evidence)

    seen = []

    async def chat(**kwargs):
        seen.append(kwargs)
        return "Review evidence", []

    monkeypatch.setattr(main, "execute_chat", chat)
    await main.chat_with_incident(
        ChatRequest(incident_id="same", investigation_id=first.investigation_id, message="explain")
    )
    assert {ev.id for ev in seen[0]["available_evidence"]} == {ev.id for ev in first.evidence}
    assert str(first.investigation_id) in seen[0]["session_id"]
    for incident, run in [("other", first.investigation_id), ("same", uuid4())]:
        with pytest.raises(HTTPException) as error:
            await main.chat_with_incident(
                ChatRequest(incident_id=incident, investigation_id=run, message="explain")
            )
        assert error.value.status_code == 404
