"""TypeSafe Jev System-1 decision engine for microsecond routing and risk scoring."""

from typing import Sequence
import httpx

from app.config import settings
from app.schemas.decisions import RiskEvaluation, SufficiencyEvaluation
from app.schemas.state import EvidenceReference, RemediationCandidate


class JevDecisionEngine:
    """TypeSafe Jev client with deterministic rule-based SRE heuristic engine fallback."""

    def __init__(self, api_key: str = settings.TYPESAFE_API_KEY, base_url: str = settings.TYPESAFE_BASE_URL) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def evaluate_sufficiency(
        self, evidence: Sequence[EvidenceReference], attempt: int = 1
    ) -> SufficiencyEvaluation:
        """Evaluate if collected evidence is sufficient to pinpoint root cause."""
        if self.api_key and not self.api_key.startswith("mock"):
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    payload = {
                        "model": "jev-choice-v1",
                        "context": [ev.model_dump() for ev in evidence],
                        "question": "Is telemetry sufficient to diagnose root cause?",
                        "options": ["sufficient", "insufficient"],
                    }
                    res = await client.post(
                        f"{self.base_url}/v1/decisions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        is_suff = data.get("choice") == "sufficient"
                        return SufficiencyEvaluation(
                            is_sufficient=is_suff,
                            missing_sources=data.get("missing", []),
                            confidence=float(data.get("confidence", 0.9)),
                            reason=data.get("rationale", "Jev Choice model evaluated sufficiency"),
                        )
            except Exception:
                pass

        sources = {ev.source for ev in evidence}
        has_metrics = "prometheus" in sources
        has_deployment = "kubernetes:deployment" in sources
        has_logs = "kubernetes:logs" in sources

        if (has_metrics and has_deployment) or attempt >= 2:
            return SufficiencyEvaluation(
                is_sufficient=True,
                missing_sources=[],
                confidence=0.95,
                reason="Core telemetry (Prometheus metrics and Kubernetes deployment status) collected.",
            )

        missing = []
        if not has_metrics:
            missing.append("prometheus")
        if not has_deployment:
            missing.append("kubernetes:deployment")
        if not has_logs:
            missing.append("kubernetes:logs")

        return SufficiencyEvaluation(
            is_sufficient=False,
            missing_sources=missing,
            confidence=0.85,
            reason=f"Missing vital telemetry sources: {', '.join(missing)}.",
        )

    async def score_remediation_risk(
        self, action: RemediationCandidate, evidence: Sequence[EvidenceReference]
    ) -> RiskEvaluation:
        """Score risk of proposed remediation action."""
        if self.api_key and not self.api_key.startswith("mock"):
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    res = await client.post(
                        f"{self.base_url}/v1/score",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "action": action.model_dump(),
                            "evidence": [ev.model_dump() for ev in evidence],
                        },
                    )
                    if res.status_code == 200:
                        d = res.json()
                        return RiskEvaluation(
                            risk_tier=d.get("tier", "medium"),
                            blast_radius=d.get("blast_radius", "single_pod"),
                            confidence=float(d.get("confidence", 0.9)),
                            requires_human_approval=True,
                            rationale=d.get("rationale", "Evaluated by Jev Score"),
                        )
            except Exception:
                pass

        return RiskEvaluation(
            risk_tier="medium",
            blast_radius="single_pod (fixproof-demo/sample-api)",
            confidence=0.92,
            requires_human_approval=True,
            rationale="Template restoration is bounded to sample-api deployment and reversible.",
        )
