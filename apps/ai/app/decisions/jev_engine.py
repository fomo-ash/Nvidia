"""TypeSafe Jev System-1 decision engine implementation.

Official documentation:
- Jev API docs: https://www.jevtypesafeai.com/jev/api
- TypeSafe AI tools & guides: https://www.typesafeai.org/tools & https://www.typesafeai.org/guides
- API Reference: https://api.typesafe.ai/ (v1/systemone)
"""

from typing import Sequence
import httpx

from app.config import settings
from app.schemas.decisions import RiskEvaluation, SufficiencyEvaluation
from app.schemas.state import EvidenceReference, RemediationCandidate


class JevDecisionEngine:
    """Official TypeSafe Jev System-1 Decision Engine for microsecond routing and risk scoring."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.EFFECTIVE_JEV_KEY
        self.base_url = (base_url or settings.TYPESAFE_BASE_URL).rstrip("/")

    def _get_api_endpoint(self) -> str:
        """Resolve either official TypeSafe endpoint or hosted gateway based on key prefix/URL."""
        if "jevtypesafeai.com" in self.base_url or self.api_key.startswith("jv_live_"):
            return "https://jevtypesafeai.com/api/v1/decide"
        return f"{self.base_url}/v1/systemone"

    async def evaluate_sufficiency(
        self, evidence: Sequence[EvidenceReference], attempt: int = 1
    ) -> SufficiencyEvaluation:
        """Evaluate if collected evidence is sufficient to pinpoint root cause using Jev noul and choice."""
        # 1. Check live Jev API if valid key is supplied
        if self.api_key and not self.api_key.startswith("mock"):
            state_text = "\n".join(
                [f"[{ev.source}] {ev.fact[:300]}" for ev in evidence if ev.mode == "live"]
            )
            payload = {
                "state": f"Incident Telemetry State:\n{state_text}",
                "questions": {
                    "is_sufficient": {
                        "type": "noul",
                        "instructions": "Is the accumulated telemetry evidence sufficient to isolate the root cause without ambiguity?",
                    },
                    "missing_source": {
                        "type": "choice",
                        "instructions": "Which telemetry source is most urgently needed to complete diagnosis?",
                        "criteria": {
                            "none": "Current evidence is sufficient",
                            "prometheus": "Missing request rate and 5xx error metrics",
                            "kubernetes_deployment": "Missing deployment pod template spec and env vars",
                            "kubernetes_logs": "Missing container error logs",
                            "direct_probe": "Missing direct health endpoint probe",
                        },
                    },
                },
            }

            try:
                endpoint = self._get_api_endpoint()
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if res.status_code == 200:
                        answers = res.json().get("answers", {})
                        noul_val = float(answers.get("is_sufficient", {}).get("noul", 0.0))
                        missing_choice = answers.get("missing_source", {}).get("choice", "none")

                        live_sources = {ev.source for ev in evidence if ev.mode == "live"}
                        is_sufficient = (
                            noul_val >= 0.70
                            and {"prometheus", "kubernetes:deployment"} <= live_sources
                        )
                        missing = []
                        if not is_sufficient and missing_choice != "none":
                            source_tag = missing_choice.replace("_", ":")
                            missing.append(source_tag)

                        return SufficiencyEvaluation(
                            is_sufficient=is_sufficient,
                            missing_sources=missing,
                            confidence=round(noul_val if is_sufficient else (1.0 - noul_val), 3),
                            reason=f"Jev System-1 evaluated sufficiency probability at {round(noul_val, 2)}.",
                        )
            except Exception:
                pass

        # 2. Deterministic high-speed rule engine fallback for local/offline dev
        sources = {ev.source for ev in evidence if ev.mode == "live"}
        has_metrics = "prometheus" in sources
        has_deployment = "kubernetes:deployment" in sources
        has_logs = "kubernetes:logs" in sources

        if has_metrics and has_deployment:
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
        """Score risk and approval requirements of proposed remediation using Jev choice and noul."""
        if self.api_key and not self.api_key.startswith("mock"):
            state_text = (
                f"Proposed Action: {action.action_type}\n"
                f"Target Parameters: {action.parameters}\n"
                f"Template Hash: {action.template_hash}\n"
                f"Reversible: {action.reversible}\n"
                f"Evidence Count: {len(evidence)}"
            )
            payload = {
                "state": f"Proposed Remediation Candidate:\n{state_text}",
                "questions": {
                    "risk_tier": {
                        "type": "choice",
                        "instructions": "What is the operational risk tier of restoring the known-good deployment template?",
                        "criteria": {
                            "low": "read-only or non-disruptive",
                            "medium": "scoped to single deployment pod template restore",
                            "high": "multi-service or database mutation",
                            "critical": "cluster-wide disruptive change",
                        },
                    },
                    "requires_human_approval": {
                        "type": "noul",
                        "instructions": "Does this production remediation action require human operator sign-off before execution?",
                    },
                },
            }

            try:
                endpoint = self._get_api_endpoint()
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if res.status_code == 200:
                        answers = res.json().get("answers", {})
                        tier_choice = answers.get("risk_tier", {}).get("choice", "medium")
                        approval_noul = float(
                            answers.get("requires_human_approval", {}).get("noul", 0.9)
                        )

                        return RiskEvaluation(
                            risk_tier=tier_choice,
                            blast_radius="single_pod (fixproof-demo/sample-api)",
                            confidence=0.92,
                            requires_human_approval=True,
                            rationale=f"Jev System-1 scored risk as '{tier_choice}' (approval probability: {round(approval_noul, 2)}).",
                        )
            except Exception:
                pass

        # Deterministic SRE policy scoring fallback
        return RiskEvaluation(
            risk_tier="medium",
            blast_radius="single_pod (fixproof-demo/sample-api)",
            confidence=0.92,
            requires_human_approval=True,
            rationale="Template restoration is bounded to sample-api deployment and reversible.",
        )
