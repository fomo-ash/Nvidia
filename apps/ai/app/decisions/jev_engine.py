"""TypeSafe Jev & Laya System-1 Decision Engine implementation.

Official Patterns & Architecture:
- Reference: https://docs.typesafe.ai/patterns
  1. Speculative Fan-out: Querying multiple parallel atomic questions (noul, choice, score)
     in a single request with zero latency penalty.
  2. Confidence-Gated Routing: Using model calibrated confidence to gate execution vs human escalation.
- Jev API docs: https://www.jevtypesafeai.com/jev/api & https://api.typesafe.ai/ (v1/systemone)
- Laya: https://laya-ai.com/ & https://huggingface.co/convaiinnovations/laya (open-source v1/systemone)
"""

from typing import Any, Sequence
import httpx

from app.config import settings
from app.schemas.decisions import RiskEvaluation, SufficiencyEvaluation
from app.schemas.state import EvidenceReference, RemediationCandidate


class JevDecisionEngine:
    """System-1 Decision Engine implementing TypeSafe Speculative Fan-Out and Confidence-Gated Routing.

    - Primary: Remote Jev API if a valid non-mock TYPESAFE_API_KEY is supplied.
    - Fallback 1: Local / In-Cluster Laya endpoint (POST /v1/systemone) via LAYA_BASE_URL.
    - Fallback 2: Deterministic SRE policy engine for offline testing and CI.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        laya_base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.EFFECTIVE_JEV_KEY
        self.base_url = (base_url or settings.TYPESAFE_BASE_URL).rstrip("/")
        self.laya_base_url = (
            laya_base_url or getattr(settings, "LAYA_BASE_URL", "http://localhost:8000")
        ).rstrip("/")

    def _get_jev_endpoint(self) -> str:
        """Resolve either official TypeSafe endpoint or hosted gateway based on key prefix/URL."""
        if "jevtypesafeai.com" in self.base_url or self.api_key.startswith("jv_live_"):
            return "https://jevtypesafeai.com/api/v1/decide"
        return f"{self.base_url}/v1/systemone"

    def _get_laya_endpoint(self) -> str:
        """Resolve Laya /v1/systemone decision endpoint."""
        return f"{self.laya_base_url}/v1/systemone"

    def _is_laya_configured(self) -> bool:
        """Check if Laya is explicitly enabled or custom endpoint supplied."""
        return bool(
            self.laya_base_url
            and (
                getattr(settings, "LAYA_ENABLED", False)
                or self.laya_base_url != getattr(settings, "LAYA_BASE_URL", "http://localhost:8000")
            )
        )

    async def _post_systemone(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Attempt HTTP POST to a /v1/systemone compliant server (Jev or Laya)."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=0.5)) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json().get("answers", {})
        except Exception:
            pass
        return None

    def _call_via_typesafe_sdk(
        self, state_text: str, questions_dict: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Optional invocation using the official typesafe-sdk if installed."""
        if not self.api_key or self.api_key.startswith("mock"):
            return None
        try:
            from typesafe_sdk import Choice, Noul, Score, TypeSafeClient  # type: ignore

            sdk_questions = {}
            for q_id, q_data in questions_dict.items():
                q_type = q_data.get("type")
                instructions = q_data.get("instructions", "")
                if q_type == "noul":
                    sdk_questions[q_id] = Noul(instructions=instructions)
                elif q_type == "choice":
                    sdk_questions[q_id] = Choice(
                        instructions=instructions, criteria=q_data.get("criteria", {})
                    )
                elif q_type == "score":
                    sdk_questions[q_id] = Score(
                        instructions=instructions, criteria=q_data.get("criteria", [])
                    )

            with TypeSafeClient(api_key=self.api_key, base_url=self.base_url) as client:
                response = client.system_one(state=state_text, questions=sdk_questions)
                answers: dict[str, Any] = {}
                for q_id in questions_dict:
                    if q_id in response.nouls:
                        answers[q_id] = {"noul": response.nouls[q_id].noul}
                    elif q_id in response.choices:
                        answers[q_id] = {
                            "choice": response.choices[q_id].choice,
                            "probabilities": response.choices[q_id].probabilities,
                        }
                    elif hasattr(response, "scores") and q_id in response.scores:
                        answers[q_id] = {"score": response.scores[q_id].score}
                return answers
        except Exception:
            return None

    async def evaluate_sufficiency(
        self, evidence: Sequence[EvidenceReference], attempt: int = 1
    ) -> SufficiencyEvaluation:
        """Evaluate evidence using Pattern 1 (Speculative Fan-out) and Pattern 2 (Confidence-Gated Routing)."""
        live_sources = {ev.source for ev in evidence if ev.mode == "live"}
        state_text = "\n".join(
            [f"[{ev.source}] {ev.fact[:300]}" for ev in evidence if ev.mode == "live"]
        )

        # Pattern 1: Speculative Fan-out: Query 4 atomic questions simultaneously in one shot
        questions = {
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
            "is_active_outage": {
                "type": "noul",
                "instructions": "Does the observed telemetry confirm that user-facing traffic is actively failing or dropping?",
            },
            "severity": {
                "type": "score",
                "instructions": "Rate the incident severity on user impact and error rate",
                "criteria": ["routine", "degraded", "severe", "critical"],
            },
        }

        answers = None
        engine_source = None

        # 1. Try official typesafe-sdk or direct Jev HTTP endpoint
        answers = self._call_via_typesafe_sdk(f"Incident Telemetry State:\n{state_text}", questions)
        if answers:
            engine_source = "TypeSafe SDK"
        elif self.api_key and not self.api_key.startswith("mock"):
            jev_headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "state": f"Incident Telemetry State:\n{state_text}",
                "questions": questions,
            }
            answers = await self._post_systemone(self._get_jev_endpoint(), jev_headers, payload)
            if answers:
                engine_source = "Jev API"

        # 2. Fallback to Laya endpoint (https://laya-ai.com /v1/systemone)
        if not answers and self._is_laya_configured():
            laya_headers = {"Content-Type": "application/json"}
            laya_key = getattr(settings, "LAYA_API_KEY", "")
            if laya_key:
                laya_headers["Authorization"] = f"Bearer {laya_key}"
            payload = {
                "state": f"Incident Telemetry State:\n{state_text}",
                "questions": questions,
            }
            answers = await self._post_systemone(self._get_laya_endpoint(), laya_headers, payload)
            if answers:
                engine_source = "Laya"

        # 3. Pattern 2: Confidence-Gated Routing on fan-out answers
        if answers:
            noul_val = float(answers.get("is_sufficient", {}).get("noul", 0.0))
            missing_choice = answers.get("missing_source", {}).get("choice", "none")
            is_active_outage = bool(float(answers.get("is_active_outage", {}).get("noul", 0.9)) >= 0.5)
            severity = answers.get("severity", {}).get("choice", "severe")

            # Confidence gate: must have >= 0.70 confidence AND physical presence of core telemetry
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
                is_active_outage=is_active_outage,
                severity_level=str(severity),
                reason=f"{engine_source} (Speculative Fan-out) evaluated sufficiency={is_sufficient} (confidence: {round(noul_val, 2)}).",
            )

        # 4. Deterministic SRE policy fallback (for offline local dev / tests)
        has_metrics = "prometheus" in live_sources
        has_deployment = "kubernetes:deployment" in live_sources
        has_logs = "kubernetes:logs" in live_sources

        if has_metrics and has_deployment:
            return SufficiencyEvaluation(
                is_sufficient=True,
                missing_sources=[],
                confidence=0.95,
                is_active_outage=True,
                severity_level="severe",
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
            is_active_outage=True,
            severity_level="severe",
            reason=f"Missing vital telemetry sources: {', '.join(missing)}.",
        )

    async def score_remediation_risk(
        self, action: RemediationCandidate, evidence: Sequence[EvidenceReference]
    ) -> RiskEvaluation:
        """Score risk and approval requirements using Speculative Fan-out & Confidence-Gated Routing."""
        state_text = (
            f"Proposed Action: {action.action_type}\n"
            f"Target Parameters: {action.parameters}\n"
            f"Template Hash: {action.template_hash}\n"
            f"Reversible: {action.reversible}\n"
            f"Evidence Count: {len(evidence)}"
        )

        # Pattern 1: Speculative Fan-out: Query risk tier, approval need, and reversibility
        questions = {
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
            "is_reversible": {
                "type": "noul",
                "instructions": "Can this template restore action be reversed if an unexpected regression occurs?",
            },
        }

        answers = None
        engine_source = None

        # 1. Try official typesafe-sdk or direct Jev HTTP endpoint
        answers = self._call_via_typesafe_sdk(f"Proposed Remediation Candidate:\n{state_text}", questions)
        if answers:
            engine_source = "TypeSafe SDK"
        elif self.api_key and not self.api_key.startswith("mock"):
            jev_headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "state": f"Proposed Remediation Candidate:\n{state_text}",
                "questions": questions,
            }
            answers = await self._post_systemone(self._get_jev_endpoint(), jev_headers, payload)
            if answers:
                engine_source = "Jev API"

        # 2. Fallback to Laya endpoint
        if not answers and self._is_laya_configured():
            laya_headers = {"Content-Type": "application/json"}
            laya_key = getattr(settings, "LAYA_API_KEY", "")
            if laya_key:
                laya_headers["Authorization"] = f"Bearer {laya_key}"
            payload = {
                "state": f"Proposed Remediation Candidate:\n{state_text}",
                "questions": questions,
            }
            answers = await self._post_systemone(self._get_laya_endpoint(), laya_headers, payload)
            if answers:
                engine_source = "Laya"

        # 3. Pattern 2: Confidence-Gated Routing on risk scoring
        if answers:
            tier_choice = answers.get("risk_tier", {}).get("choice", "medium")
            approval_noul = float(answers.get("requires_human_approval", {}).get("noul", 0.9))
            is_reversible = bool(float(answers.get("is_reversible", {}).get("noul", 0.9)) >= 0.5)

            # Confidence-gated routing: any mutation or moderate risk enforces human approval
            requires_human_approval = True if tier_choice in ("medium", "high", "critical") else (approval_noul >= 0.5)

            return RiskEvaluation(
                risk_tier=tier_choice,
                blast_radius="single_pod (fixproof-demo/sample-api)",
                confidence=0.92,
                requires_human_approval=requires_human_approval,
                is_reversible=is_reversible,
                rationale=f"{engine_source} Confidence-Gated Routing scored risk as '{tier_choice}' (approval confidence: {round(approval_noul, 2)}).",
            )

        # 4. Deterministic SRE policy scoring fallback
        return RiskEvaluation(
            risk_tier="medium",
            blast_radius="single_pod (fixproof-demo/sample-api)",
            confidence=0.92,
            requires_human_approval=True,
            is_reversible=True,
            rationale="Template restoration is bounded to sample-api deployment and reversible.",
        )
