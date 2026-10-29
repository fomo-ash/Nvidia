"""Bounded System-1 decisions with explicit provider selection and policy fallback."""

from typing import Any, Literal, Sequence, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import settings
from app.schemas.decisions import RiskEvaluation, SufficiencyEvaluation
from app.schemas.state import EvidenceReference, RemediationCandidate

System1Provider = Literal["policy", "jev", "laya"]
Severity = Literal["routine", "degraded", "severe", "critical"]


class _NoulAnswer(BaseModel):
    noul: float = Field(ge=0.0, le=1.0)


class _ChoiceAnswer(BaseModel):
    choice: Literal[
        "none",
        "prometheus",
        "kubernetes_deployment",
        "kubernetes_logs",
        "direct_probe",
    ]


class _SeverityAnswer(BaseModel):
    choice: Severity | None = None
    score: Severity | None = None

    @model_validator(mode="after")
    def require_value(self):
        if self.choice is None and self.score is None:
            raise ValueError("severity must include choice or score")
        if self.choice is not None and self.score is not None and self.choice != self.score:
            raise ValueError("severity choice and score disagree")
        return self

    @property
    def value(self) -> Severity:
        value = self.choice or self.score
        if value is None:  # pragma: no cover - enforced by the model validator
            raise ValueError("severity is missing")
        return value


class _SufficiencyAnswers(BaseModel):
    is_sufficient: _NoulAnswer
    missing_source: _ChoiceAnswer
    is_active_outage: _NoulAnswer
    severity: _SeverityAnswer


class _RiskChoiceAnswer(BaseModel):
    choice: Literal["low", "medium", "high", "critical"]


class _RiskAnswers(BaseModel):
    risk_tier: _RiskChoiceAnswer
    requires_human_approval: _NoulAnswer
    is_reversible: _NoulAnswer


AnswersModel = TypeVar("AnswersModel", bound=BaseModel)


class JevDecisionEngine:
    """Evaluate advisory decisions through policy, Jev, or a compatible HTTP service.

    Provider behavior is explicit:

    - ``policy`` performs no outbound request.
    - ``laya`` calls the configured ``/v1/systemone`` endpoint, then falls back to policy.
    - ``jev`` calls Jev when a live key exists. When ``LAYA_ENABLED`` is true it may try the
      compatible endpoint next; otherwise it falls back directly to policy.

    External answers are advisory and schema-validated. They never remove the human-approval
    requirement for a remediation candidate.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        laya_base_url: str | None = None,
        provider: System1Provider | None = None,
    ) -> None:
        self.api_key = api_key or settings.EFFECTIVE_JEV_KEY
        self.base_url = (base_url or settings.TYPESAFE_BASE_URL).rstrip("/")
        self.laya_base_url = (laya_base_url or settings.LAYA_BASE_URL).rstrip("/")
        self.provider: System1Provider = provider or settings.SYSTEM1_PROVIDER

    @property
    def _has_live_jev_key(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("mock"))

    def _get_jev_endpoint(self) -> str:
        """Resolve the configured Jev HTTP endpoint."""
        if "jevtypesafeai.com" in self.base_url or self.api_key.startswith("jv_live_"):
            return "https://jevtypesafeai.com/api/v1/decide"
        return f"{self.base_url}/v1/systemone"

    def _get_laya_endpoint(self) -> str:
        """Resolve the configured System-1-compatible HTTP endpoint."""
        return f"{self.laya_base_url}/v1/systemone"

    async def _post_systemone(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Return only a structurally valid answer mapping from a compatible endpoint."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=0.5)) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, TypeError, ValueError):
            return None
        if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
            return None
        return body["answers"]

    def _call_via_typesafe_sdk(
        self, state_text: str, questions: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Use the optional TypeSafe SDK when installed, normalizing its answer shape."""
        if not self._has_live_jev_key:
            return None
        try:
            from typesafe_sdk import Choice, Noul, Score, TypeSafeClient  # type: ignore

            sdk_questions = {}
            for question_id, question in questions.items():
                question_type = question.get("type")
                instructions = question.get("instructions", "")
                if question_type == "noul":
                    sdk_questions[question_id] = Noul(instructions=instructions)
                elif question_type == "choice":
                    sdk_questions[question_id] = Choice(
                        instructions=instructions,
                        criteria=question.get("criteria", {}),
                    )
                elif question_type == "score":
                    sdk_questions[question_id] = Score(
                        instructions=instructions,
                        criteria=question.get("criteria", []),
                    )

            with TypeSafeClient(api_key=self.api_key, base_url=self.base_url) as client:
                response = client.system_one(state=state_text, questions=sdk_questions)
                answers: dict[str, Any] = {}
                for question_id in questions:
                    if question_id in response.nouls:
                        answers[question_id] = {"noul": response.nouls[question_id].noul}
                    elif question_id in response.choices:
                        answers[question_id] = {
                            "choice": response.choices[question_id].choice,
                        }
                    elif hasattr(response, "scores") and question_id in response.scores:
                        # Normalize SDK score answers to the HTTP compatibility shape.
                        answers[question_id] = {
                            "choice": response.scores[question_id].score,
                        }
                return answers
        # The SDK is optional and may raise provider-specific transport exceptions. This boundary
        # must fail closed into the validated HTTP path or deterministic policy.
        except Exception:
            return None

    @staticmethod
    def _validate_answers(
        raw_answers: dict[str, Any] | None, schema: type[AnswersModel]
    ) -> AnswersModel | None:
        if raw_answers is None:
            return None
        try:
            return schema.model_validate(raw_answers)
        except ValidationError:
            return None

    async def _query_answers(
        self,
        state_text: str,
        questions: dict[str, Any],
        schema: type[AnswersModel],
    ) -> tuple[str | None, AnswersModel | None]:
        """Query only selected providers and accept only validated complete answers."""
        payload = {"state": state_text, "questions": questions}

        if self.provider == "policy":
            return None, None

        if self.provider == "jev" and self._has_live_jev_key:
            raw_answers = self._call_via_typesafe_sdk(state_text, questions)
            parsed = self._validate_answers(raw_answers, schema)
            if parsed is not None:
                return "TypeSafe SDK", parsed

            raw_answers = await self._post_systemone(
                self._get_jev_endpoint(),
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                payload,
            )
            parsed = self._validate_answers(raw_answers, schema)
            if parsed is not None:
                return "Jev API", parsed

        should_try_laya = self.provider == "laya" or (
            self.provider == "jev" and settings.LAYA_ENABLED
        )
        if should_try_laya:
            headers = {"Content-Type": "application/json"}
            if settings.LAYA_API_KEY:
                headers["Authorization"] = f"Bearer {settings.LAYA_API_KEY}"
            raw_answers = await self._post_systemone(self._get_laya_endpoint(), headers, payload)
            parsed = self._validate_answers(raw_answers, schema)
            if parsed is not None:
                return "System-1 compatible service", parsed

        return None, None

    @staticmethod
    def _live_sources(evidence: Sequence[EvidenceReference]) -> set[str]:
        """Count only live, trusted observations toward the physical-evidence gate."""
        return {item.source for item in evidence if item.mode == "live" and item.trusted}

    @staticmethod
    def _physical_gaps(live_sources: set[str]) -> list[str]:
        gaps = []
        if "prometheus" not in live_sources:
            gaps.append("prometheus")
        if "kubernetes:deployment" not in live_sources:
            gaps.append("kubernetes:deployment")
        return gaps

    @classmethod
    def _policy_sufficiency(cls, live_sources: set[str]) -> SufficiencyEvaluation:
        missing = cls._physical_gaps(live_sources)
        if not missing:
            return SufficiencyEvaluation(
                is_sufficient=True,
                missing_sources=[],
                confidence=1.0,
                is_active_outage=False,
                severity_level="unknown",
                reason=(
                    "Deterministic policy found the required trusted source types. "
                    "It did not assess outage status or severity."
                ),
            )
        return SufficiencyEvaluation(
            is_sufficient=False,
            missing_sources=missing,
            confidence=1.0,
            is_active_outage=False,
            severity_level="unknown",
            reason=f"Deterministic policy requires: {', '.join(missing)}.",
        )

    async def evaluate_sufficiency(
        self, evidence: Sequence[EvidenceReference], attempt: int = 1
    ) -> SufficiencyEvaluation:
        """Evaluate evidence without allowing a provider to bypass physical source checks."""
        del attempt  # retained for the graph call contract
        live_sources = self._live_sources(evidence)
        state_text = "\n".join(
            f"[{item.source}] {item.fact[:300]}"
            for item in evidence
            if item.mode == "live" and item.trusted
        )
        questions = {
            "is_sufficient": {
                "type": "noul",
                "instructions": ("Is the accumulated telemetry sufficient to isolate root cause?"),
            },
            "missing_source": {
                "type": "choice",
                "instructions": "Which telemetry source is most urgently needed?",
                "criteria": {
                    "none": "Current evidence is sufficient",
                    "prometheus": "Missing request and error metrics",
                    "kubernetes_deployment": "Missing deployment state",
                    "kubernetes_logs": "Missing bounded container logs",
                    "direct_probe": "Missing a direct health probe",
                },
            },
            "is_active_outage": {
                "type": "noul",
                "instructions": "Does evidence confirm actively failing user traffic?",
            },
            "severity": {
                "type": "score",
                "instructions": "Classify severity from measured user impact",
                "criteria": ["routine", "degraded", "severe", "critical"],
            },
        }
        source, answers = await self._query_answers(
            f"Incident telemetry:\n{state_text}", questions, _SufficiencyAnswers
        )
        if source is None or answers is None:
            return self._policy_sufficiency(live_sources)

        physical_gaps = self._physical_gaps(live_sources)
        is_sufficient = answers.is_sufficient.noul >= 0.70 and not physical_gaps
        missing = list(physical_gaps)
        selected_gap = answers.missing_source.choice.replace("_", ":")
        if not is_sufficient and selected_gap != "none" and selected_gap not in missing:
            missing.append(selected_gap)

        return SufficiencyEvaluation(
            is_sufficient=is_sufficient,
            missing_sources=missing,
            confidence=answers.is_sufficient.noul,
            is_active_outage=answers.is_active_outage.noul >= 0.5,
            severity_level=answers.severity.value,
            reason=(
                f"{source} returned validated advisory answers; "
                f"physical evidence gate passed={not physical_gaps}."
            ),
        )

    async def score_remediation_risk(
        self, action: RemediationCandidate, evidence: Sequence[EvidenceReference]
    ) -> RiskEvaluation:
        """Score advisory risk while keeping explicit human approval mandatory."""
        state_text = (
            f"Proposed Action: {action.action_type}\n"
            f"Target Parameters: {action.parameters}\n"
            f"Template Hash: {action.template_hash}\n"
            f"Reversible: {action.reversible}\n"
            f"Evidence Count: {len(evidence)}"
        )
        questions = {
            "risk_tier": {
                "type": "choice",
                "instructions": "Classify the operational risk tier",
                "criteria": {
                    "low": "read-only or non-disruptive",
                    "medium": "single deployment template restore",
                    "high": "multi-service or data mutation",
                    "critical": "cluster-wide disruptive change",
                },
            },
            "requires_human_approval": {
                "type": "noul",
                "instructions": "Does this remediation require operator approval?",
            },
            "is_reversible": {
                "type": "noul",
                "instructions": "Can this action be reversed without state loss?",
            },
        }
        source, answers = await self._query_answers(
            f"Proposed remediation:\n{state_text}", questions, _RiskAnswers
        )
        if source is None or answers is None:
            return RiskEvaluation(
                risk_tier="medium",
                blast_radius="single_deployment (fixproof-demo/sample-api)",
                confidence=1.0,
                requires_human_approval=True,
                is_reversible=action.reversible,
                rationale=(
                    "Deterministic policy requires human approval; no validated external "
                    "risk assessment was accepted."
                ),
            )

        return RiskEvaluation(
            risk_tier=answers.risk_tier.choice,
            blast_radius="single_deployment (fixproof-demo/sample-api)",
            confidence=answers.requires_human_approval.noul,
            requires_human_approval=True,
            is_reversible=answers.is_reversible.noul >= 0.5,
            rationale=(
                f"{source} returned a validated advisory risk assessment. "
                "FixProof policy still requires explicit human approval."
            ),
        )
