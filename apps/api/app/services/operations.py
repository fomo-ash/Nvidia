"""Durable lifecycle contract. The default adapter never mutates infrastructure."""

from typing import Literal, Protocol
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator
from sqlalchemy import select

from app.models.domain import (
    Approval,
    Execution,
    Incident,
    Recommendation,
    TrustedBaseline,
    VerificationResult,
    now,
)
from app.core.time import utc
from app.schemas.lifecycle import ExecutionOut, VerificationOut
from app.services.idempotency import finish, reserve
from app.services.recommendations import audit, require_incident, validate_current


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["succeeded", "failed"]
    details: dict[str, JsonValue]


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=200)
    observed_at: AwareDatetime
    value: float = Field(allow_inf_nan=False)
    threshold: float = Field(allow_inf_nan=False)
    operator: Literal["lt", "lte", "gt", "gte", "eq"]

    def passes(self):
        return {
            "lt": self.value < self.threshold,
            "lte": self.value <= self.threshold,
            "gt": self.value > self.threshold,
            "gte": self.value >= self.threshold,
            "eq": self.value == self.threshold,
        }[self.operator]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["passed", "failed", "inconclusive"]
    details: dict[str, JsonValue]
    mode: Literal["synthetic", "live", "unavailable", "unknown"] = "unknown"
    measurements: list[Measurement] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def backed_by_measurements(self):
        if self.status != "inconclusive":
            if not self.measurements or self.mode not in {"synthetic", "live"}:
                raise ValueError("A verification outcome requires attributable measurements")
            if self.mode == "live":
                expected = {
                    "rollout_available": ("kubernetes:deployment", "gte", None),
                    **{f"health_probe_{index}": ("direct:probe", "eq", 200)
                       for index in range(1, 4)},
                    "work_requests": ("prometheus", "gte", 20),
                    "http_5xx_ratio": ("prometheus", "lt", 0.01),
                }
                names = [measurement.name for measurement in self.measurements]
                if len(names) != len(set(names)) or any(name not in expected for name in names):
                    raise ValueError("Unexpected live recovery measurement")
                for measurement in self.measurements:
                    source, operator, threshold = expected[measurement.name]
                    if (
                        measurement.source != source
                        or measurement.operator != operator
                        or (threshold is not None and measurement.threshold != threshold)
                        or (measurement.name == "rollout_available" and measurement.threshold < 1)
                    ):
                        raise ValueError("Live recovery measurement contract changed")
                if self.status == "passed" and set(names) != set(expected):
                    raise ValueError("Passed live recovery requires all six measurements")
            passed = all(measurement.passes() for measurement in self.measurements)
            if (self.status == "passed") != passed:
                raise ValueError("Verification status contradicts its measurements")
        return self


class OperationsAdapter(Protocol):
    name: str

    def execute(self, execution: Execution) -> ActionResult: ...
    def verify(self, execution: Execution) -> Observation: ...


class UnconfiguredAdapter:
    name = "unconfigured"

    def execute(self, execution):
        return ActionResult(
            status="failed",
            details={
                "reason": "No action adapter is configured",
                "mutation_performed": False,
                "mode": "unavailable",
            },
        )

    def verify(self, execution):
        return Observation(
            status="inconclusive",
            mode="unavailable",
            details={
                "reason": "No independent measurement adapter is configured",
                "mode": "unavailable",
            },
        )


def get_operations_adapter() -> OperationsAdapter:
    from app.core.config import settings

    if settings.live_execution_enabled and len(settings.execution_signing_key) >= 32:
        return LiveKindAdapter()
    return UnconfiguredAdapter()


class LiveKindAdapter:
    name = "kind_restore"

    def execute(self, execution):
        from app.core.config import settings
        from app.services.capability import issue
        from app.services.live_evidence import post

        params = execution.parameters
        return ActionResult.model_validate(
            post(
                settings.mcp_server_url.rstrip("/") + "/internal/restore_known_good_template",
                {
                    "execution_id": str(execution.id),
                    "proposal_hash": execution.proposal_hash,
                    "namespace": params["namespace"],
                    "deployment": params["deployment"],
                    "uid": params["uid"],
                    "resource_version": params["resource_version"],
                    "expected_bad_template_hash": params["expected_bad_template_hash"],
                    "desired_good_template_hash": params["desired_good_template_hash"],
                    "desired_template": params["desired_template"],
                    "capability_token": issue(execution),
                },
                timeout=15,
            )
        )

    def verify(self, execution):
        from app.core.config import settings
        from app.services.live_evidence import post

        return Observation.model_validate(
            post(
                settings.mcp_server_url.rstrip("/") + "/internal/verify_recovery",
                {
                    "uid": execution.parameters["uid"],
                    "execution_id": str(execution.id),
                    "desired_good_template_hash": execution.parameters["desired_good_template_hash"],
                    "after": utc(execution.completed_at).isoformat(),
                },
                timeout=130,
            )
        )


def execute(db, actor, key, recommendation_id, expected_hash, adapter):
    record, replay = reserve(
        db,
        actor,
        key,
        f"/recommendations/{recommendation_id}/execute",
        {"proposal_hash": expected_hash},
    )
    if replay is not None:
        return replay
    item = db.get(Recommendation, recommendation_id)
    if item is None:
        raise HTTPException(404, "Recommendation not found")
    incident = db.get(Incident, item.incident_id)
    if incident.mode == "live" and adapter.name != "kind_restore":
        raise HTTPException(
            409, "Live execution is disabled pending scoped capability and preflight"
        )
    if incident.mode != "live" and adapter.name == "kind_restore":
        adapter = UnconfiguredAdapter()
    require_incident(db, item.incident_id, lock=True)
    db.refresh(item)
    if item.status != "approved":
        raise HTTPException(409, "Only approved recommendations can execute")
    validate_current(db, item, expected_hash)
    approval = db.scalar(select(Approval).where(Approval.recommendation_id == item.id))
    if (
        approval is None
        or approval.decision != "approved"
        or approval.proposal_hash != item.proposal_hash
        or approval.recommendation_version != item.version
        or not approval.expires_at
        or utc(approval.expires_at) <= now()
    ):
        raise HTTPException(409, "No current exact approval record authorizes this action")
    if db.scalar(select(Execution.id).where(Execution.recommendation_id == item.id)):
        raise HTTPException(409, "This recommendation already has an execution attempt")
    parameters = dict(item.parameters)
    if incident.mode == "live":
        baseline = db.get(TrustedBaseline, UUID(parameters["trusted_baseline_id"]))
        if baseline is None:
            raise HTTPException(409, "Trusted baseline unavailable")
        parameters["desired_template"] = baseline.template
    execution = Execution(
        recommendation_id=item.id,
        approval_id=approval.id,
        actor=actor.id,
        proposal_hash=item.proposal_hash,
        action=item.action,
        target=item.target,
        parameters=parameters,
        adapter=adapter.name,
        status="pending",
        result={},
    )
    db.add(execution)
    db.flush()
    incident_id = item.incident_id
    audit(
        db,
        "execution",
        execution.id,
        "execution_started",
        {"incident_id": str(incident_id), "recommendation_id": str(item.id)},
        actor.id,
    )
    # Commit the claim BEFORE invoking the adapter. Crashes leave a visible pending
    # operation; replay cannot invoke it again. No automatic recovery/retry is implied.
    finish(record, ExecutionOut.model_validate(execution).model_dump(mode="json"), 202)
    db.commit()
    try:
        result = ActionResult.model_validate(adapter.execute(execution))
    except Exception:
        if incident.mode == "live":
            require_incident(db, incident_id, lock=True)
            db.refresh(execution)
            execution.result = {
                "reason": "Action outcome unknown; reconcile before any further work",
                "outcome_unknown": True,
            }
            audit(
                db,
                "execution",
                execution.id,
                "execution_outcome_unknown",
                {"incident_id": str(incident_id), "recommendation_id": str(item.id)},
                actor.id,
            )
            db.flush()
            value = ExecutionOut.model_validate(execution).model_dump(mode="json")
            finish(record, value, 202)
            db.commit()
            return JSONResponse(value, status_code=202)
        # Never expose adapter exceptions (they can contain credentials).
        result = ActionResult(
            status="failed",
            details={
                "reason": "Action adapter failed; outcome may be unknown",
                "mode": "unknown",
                "outcome_unknown": True,
            },
        )
    require_incident(db, incident_id, lock=True)
    db.refresh(execution)
    db.refresh(item)
    execution.status, execution.result, execution.completed_at = (
        result.status,
        result.details,
        now(),
    )
    item.status = "executed" if result.status == "succeeded" else "execution_failed"
    audit(
        db,
        "execution",
        execution.id,
        f"execution_{result.status}",
        {"incident_id": str(incident_id), "recommendation_id": str(item.id)},
        actor.id,
    )
    db.flush()
    value = ExecutionOut.model_validate(execution).model_dump(mode="json")
    finish(record, value, 201)
    db.commit()
    return JSONResponse(value, status_code=201)


def reconcile(db, execution_id, actor):
    """Observe a pending live action; never submit another patch."""
    from app.services.live_evidence import LiveReader

    execution = db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(404, "Execution not found")
    item = db.get(Recommendation, execution.recommendation_id)
    incident = require_incident(db, item.incident_id, lock=True)
    if incident.mode != "live" or execution.adapter != "kind_restore":
        raise HTTPException(409, "Only pending live executions can be reconciled")
    db.refresh(execution)
    if execution.status != "pending":
        return execution
    try:
        observed = LiveReader().collect("kubernetes:deployment", execution.parameters["uid"])[
            "raw_data"
        ]
    except Exception as exc:
        raise HTTPException(409, "Current Deployment could not be checked") from exc
    params = execution.parameters
    if observed.get("uid") != params["uid"]:
        raise HTTPException(409, "Target UID changed; execution outcome remains unknown")
    if (
        observed.get("execution_id") == str(execution.id)
        and observed.get("template_hash") == params["desired_good_template_hash"]
    ):
        execution.status = "succeeded"
        execution.result = {
            "reason": "Exact patch confirmed by Deployment execution marker and template",
            "mutation_performed": True,
            "resource_version": observed.get("resource_version"),
            "revision": observed.get("revision"),
        }
        item.status = "executed"
    elif (
        observed.get("execution_id") != str(execution.id)
        and observed.get("template_hash") == params["expected_bad_template_hash"]
        and observed.get("resource_version") == params["resource_version"]
    ):
        execution.status = "failed"
        execution.result = {
            "reason": "No patch observed at the original resource version",
            "mutation_performed": False,
        }
        item.status = "execution_failed"
    else:
        return execution
    execution.completed_at = now()
    audit(
        db,
        "execution",
        execution.id,
        "execution_reconciled",
        {
            "incident_id": str(incident.id),
            "status": execution.status,
        },
        actor.id,
    )
    return execution


def verify(db, actor, key, execution_id, adapter):
    record, replay = reserve(db, actor, key, f"/executions/{execution_id}/verify", {})
    if replay is not None:
        return replay
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(404, "Execution not found")
    item = db.get(Recommendation, execution.recommendation_id)
    require_incident(db, item.incident_id, lock=True)
    db.refresh(execution)
    if execution.status != "succeeded":
        raise HTTPException(409, "Only successful executions can be independently verified")
    if execution.adapter != adapter.name:
        raise HTTPException(409, "Execution adapter is no longer available")
    if db.scalar(
        select(VerificationResult.id).where(VerificationResult.execution_id == execution.id)
    ):
        raise HTTPException(409, "Execution already has a verification attempt")
    verification = VerificationResult(
        execution_id=execution.id, actor=actor.id, status="pending", observations={}
    )
    db.add(verification)
    db.flush()
    incident_id = item.incident_id
    audit(
        db,
        "verification",
        verification.id,
        "verification_started",
        {"incident_id": str(incident_id), "execution_id": str(execution.id)},
        actor.id,
    )
    finish(record, VerificationOut.model_validate(verification).model_dump(mode="json"), 202)
    db.commit()
    try:
        result = Observation.model_validate(adapter.verify(execution))
        if result.status != "inconclusive":
            completed = utc(execution.completed_at)
            if any(
                m.observed_at < completed or m.observed_at > now() + timedelta(minutes=1)
                for m in result.measurements
            ):
                raise ValueError("Verification measurements must be fresh and follow execution")
    except Exception:
        result = Observation(
            status="inconclusive",
            details={"reason": "Independent verification adapter failed", "mode": "unknown"},
        )
    require_incident(db, incident_id, lock=True)
    db.refresh(verification)
    db.refresh(item)
    verification.status, verification.observations, verification.completed_at = (
        result.status,
        result.model_dump(mode="json"),
        now(),
    )
    if result.status != "inconclusive":
        item.status = "verified" if result.status == "passed" else "verification_failed"
    audit(
        db,
        "verification",
        verification.id,
        f"verification_{result.status}",
        {"incident_id": str(incident_id), "execution_id": str(execution.id)},
        actor.id,
    )
    db.flush()
    value = VerificationOut.model_validate(verification).model_dump(mode="json")
    finish(record, value, 201)
    db.commit()
    return JSONResponse(value, status_code=201)
