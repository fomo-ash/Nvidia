"""Read-only live proposal construction from operator trust and retained evidence."""

import copy
import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import settings
from app.core.time import utc
from app.models.domain import (
    EvidenceItem,
    Incident,
    Investigation,
    Recommendation,
    TrustedBaseline,
    now,
)
from app.schemas.analysis import AnalysisResult
from app.services.idempotency import digest
from app.services.recommendations import audit, proposal_digest, require_incident

TARGET = ("local-kind", "fixproof-demo", "sample-api")


def template_hash(template: dict) -> str:
    return hashlib.sha256(
        json.dumps(template, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def faulty_template(good: dict) -> dict:
    bad = copy.deepcopy(good)
    try:
        containers = bad["spec"]["containers"]
        if len(containers) != 1 or containers[0]["name"] != "sample-api":
            raise ValueError("Unexpected containers")
        modes = [value for value in containers[0]["env"] if value.get("name") == "FAIL_MODE"]
        if len(modes) != 1 or modes[0].get("value") != "off":
            raise ValueError("Known-good mode is not off")
        modes[0]["value"] = "on"
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise HTTPException(422, "Template is not the known-good sample workload") from exc
    return bad


def register_baseline(db, payload, actor):
    if actor.id == "local-demo-user":
        raise HTTPException(401, "Operator session required")
    if settings.sample_cluster_id != TARGET[0] or payload.target_uid != settings.sample_target_uid:
        raise HTTPException(409, "Target UID differs from registration")
    if not isinstance(payload.template, dict) or len(json.dumps(payload.template)) > 32768:
        raise HTTPException(422, "Template exceeds the sample bound")
    faulty_template(payload.template)
    if template_hash(payload.template) != payload.template_hash:
        raise HTTPException(422, "Trusted template hash mismatch")
    existing = db.scalar(
        select(TrustedBaseline).where(TrustedBaseline.target_uid == payload.target_uid)
    )
    if existing:
        if existing.template_hash != payload.template_hash or existing.template != payload.template:
            raise HTTPException(409, "A different baseline is already registered for this UID")
        return existing
    item = TrustedBaseline(
        id=uuid4(),
        cluster=TARGET[0],
        namespace=TARGET[1],
        deployment=TARGET[2],
        target_uid=payload.target_uid,
        template=payload.template,
        template_hash=payload.template_hash,
        registered_by=actor.id,
    )
    db.add(item)
    db.flush()
    audit(db, "trusted_baseline", item.id, "registered", {"target_uid": item.target_uid}, actor.id)
    return item


def _retained(item: EvidenceItem) -> bool:
    canonical = {
        "source": item.source,
        "observed_at": utc(item.observed_at).isoformat(),
        "fact": item.fact,
        "raw_data": item.raw_data,
        "transport_id": item.transport_id,
        "transport_hash": item.transport_hash,
        "target_uid": item.target_uid,
        "mode": item.mode,
        "trust_label": item.trust_label,
        "redacted": item.redacted,
        "collection_error": item.collection_error,
    }
    return digest(canonical) == item.content_hash


def propose(db, incident_id: UUID, investigation_id: UUID, actor):
    if actor.id == "local-demo-user":
        raise HTTPException(401, "Operator session required")
    incident = require_incident(db, incident_id, lock=True)
    if (
        incident.mode != "live"
        or incident.lifecycle != "open"
        or incident.target_id != "local-kind/fixproof-demo/sample-api"
        or incident.target_uid != settings.sample_target_uid
    ):
        raise HTTPException(409, "Incident is not the current registered live target")
    run = db.get(Investigation, investigation_id)
    if run is None or run.incident_id != incident.id or run.mode != "live":
        raise HTTPException(404, "Live investigation not found")
    if run.status != "completed" or incident.assessment != "active":
        raise HTTPException(409, "Live investigation is not ready for a restore proposal")
    latest = db.scalar(
        select(Investigation)
        .where(Investigation.incident_id == incident.id)
        .order_by(Investigation.created_at.desc(), Investigation.id.desc())
        .limit(1)
    )
    if latest.id != run.id:
        raise HTTPException(409, "A newer investigation exists")
    if run.result.get("gaps") or run.result.get("assessment") != "active":
        raise HTTPException(409, "Investigation has gaps or no active fault")
    try:
        analysis = AnalysisResult.model_validate(run.result["analysis"])
        analysis.analysis.validate_advisory()
    except Exception as exc:
        raise HTTPException(409, "Validated analysis is unavailable") from exc
    if analysis.analysis.advisory_action != "restore_known_good_template":
        raise HTTPException(409, "No supported restore action was suggested")
    baseline = db.scalar(
        select(TrustedBaseline).where(TrustedBaseline.target_uid == incident.target_uid)
    )
    if baseline is None or template_hash(baseline.template) != baseline.template_hash:
        raise HTTPException(409, "Trusted baseline is unavailable or changed")
    rows = db.scalars(select(EvidenceItem).where(EvidenceItem.investigation_id == run.id)).all()
    if any(
        row.mode != "live"
        or row.target_uid != incident.target_uid
        or row.collection_error
        or row.trust_label != "untrusted"
        or not _retained(row)
        for row in rows
    ):
        raise HTTPException(409, "Retained evidence is incomplete or changed")
    by_source = {row.source: row for row in rows}
    if not {"kubernetes:deployment", "prometheus", "direct:probe"} <= by_source.keys():
        raise HTTPException(409, "Required physical evidence is missing")
    known_ids = {row.id for row in rows}
    if any(
        not set(finding.supporting_evidence_ids + finding.contradicting_evidence_ids) <= known_ids
        for finding in analysis.analysis.hypotheses
    ):
        raise HTTPException(409, "Analysis cites evidence outside the retained run")
    deployment = by_source["kubernetes:deployment"].raw_data
    bad_hash = template_hash(faulty_template(baseline.template))
    if (
        deployment.get("uid") != incident.target_uid
        or deployment.get("namespace") != TARGET[1]
        or deployment.get("deployment_name") != TARGET[2]
        or deployment.get("template_hash") != bad_hash
        or not deployment.get("resource_version")
    ):
        raise HTTPException(409, "Observed Deployment differs from the exact faulty template")
    prior = db.scalar(select(Recommendation).where(Recommendation.investigation_id == run.id))
    if prior:
        return prior
    version = (
        db.scalar(
            select(func.max(Recommendation.version)).where(
                Recommendation.incident_id == incident.id
            )
        )
        or 0
    ) + 1
    for previous in db.scalars(
        select(Recommendation).where(
            Recommendation.incident_id == incident.id,
            Recommendation.status.in_(["proposed", "approved"]),
        )
    ):
        previous.status = "superseded"
        audit(
            db,
            "recommendation",
            previous.id,
            "superseded",
            {"replacement_version": version},
            actor.id,
        )
    item = Recommendation(
        id=uuid4(),
        incident_id=incident.id,
        investigation_id=run.id,
        version=version,
        action="restore_known_good_template",
        target="local-kind/fixproof-demo/sample-api",
        parameters={
            "cluster": TARGET[0],
            "namespace": TARGET[1],
            "deployment": TARGET[2],
            "uid": incident.target_uid,
            "resource_version": deployment["resource_version"],
            "expected_bad_template_hash": bad_hash,
            "desired_good_template_hash": baseline.template_hash,
            "trusted_baseline_id": str(baseline.id),
            "analysis_hash": digest(run.result["analysis"]),
            "verification_plan": "Fresh rollout, three health probes and 60 seconds of work traffic",
        },
        evidence=[
            {"id": str(row.id), "source": row.source, "content_hash": row.content_hash}
            for row in sorted(rows, key=lambda row: row.source)
        ],
        expires_at=now() + timedelta(seconds=settings.proposal_ttl_seconds),
    )
    item.proposal_hash = proposal_digest(item)
    db.add(item)
    db.flush()
    audit(
        db,
        "recommendation",
        item.id,
        "proposed",
        {
            "incident_id": str(incident.id),
            "investigation_id": str(run.id),
            "version": version,
            "proposal_hash": item.proposal_hash,
        },
        actor.id,
    )
    return item


def validate_live_current(db, item: Recommendation):
    """Recheck persisted bindings and the live Deployment before human approval."""
    from app.services.live_evidence import LiveReader

    incident = db.get(Incident, item.incident_id)
    if (
        incident is None
        or incident.mode != "live"
        or incident.lifecycle != "open"
        or incident.target_uid != settings.sample_target_uid
        or item.action != "restore_known_good_template"
        or item.target != "local-kind/fixproof-demo/sample-api"
        or item.parameters.get("uid") != incident.target_uid
    ):
        raise HTTPException(409, "Live proposal target changed")
    baseline = db.get(TrustedBaseline, UUID(item.parameters["trusted_baseline_id"]))
    if (
        baseline is None
        or baseline.target_uid != incident.target_uid
        or template_hash(baseline.template) != baseline.template_hash
        or item.parameters.get("desired_good_template_hash") != baseline.template_hash
        or item.parameters.get("expected_bad_template_hash")
        != template_hash(faulty_template(baseline.template))
    ):
        raise HTTPException(409, "Trusted baseline changed")
    run = db.get(Investigation, item.investigation_id)
    if (
        run is None
        or run.status != "completed"
        or run.mode != "live"
        or item.parameters.get("analysis_hash") != digest(run.result.get("analysis"))
    ):
        raise HTTPException(409, "Retained investigation changed")
    try:
        advice = AnalysisResult.model_validate(run.result["analysis"]).analysis
        advice.validate_advisory()
        if (
            run.result.get("gaps")
            or advice.gaps
            or advice.advisory_action != "restore_known_good_template"
        ):
            raise ValueError("Advice requires review")
    except (ValueError, KeyError) as exc:
        raise HTTPException(409, "Retained analysis requires manual review") from exc
    rows = db.scalars(select(EvidenceItem).where(EvidenceItem.investigation_id == run.id)).all()
    expected = sorted(
        (
            {"id": str(row.id), "source": row.source, "content_hash": row.content_hash}
            for row in rows
        ),
        key=lambda entry: entry["source"],
    )
    if any(row.collection_error or not _retained(row) for row in rows) or item.evidence != expected:
        raise HTTPException(409, "Retained evidence changed")
    try:
        observed = LiveReader().collect("kubernetes:deployment", incident.target_uid)["raw_data"]
    except Exception as exc:
        raise HTTPException(409, "Current Deployment could not be checked") from exc
    if (
        observed.get("uid") != incident.target_uid
        or observed.get("resource_version") != item.parameters.get("resource_version")
        or observed.get("template_hash") != item.parameters.get("expected_bad_template_hash")
    ):
        raise HTTPException(409, "Deployment changed since the proposal")
