"""Durable leased read-only investigations. Run with python -m app.worker."""

from datetime import datetime, timedelta, timezone
import json
import math
import time
from uuid import uuid4, uuid5

from sqlalchemy import or_, select

from app.core.config import settings
from app.core.time import utc
from app.db.session import SessionLocal
from app.models.domain import Incident, Investigation, InvestigationRequest, EvidenceItem
from app.schemas.analysis import AnalysisResult
from app.services.idempotency import digest
from app.services.live_evidence import LiveReader, TOOLS
from app.services.recommendations import audit


def claim(factory):
    stamp = datetime.now(timezone.utc)
    cutoff = stamp - timedelta(seconds=settings.investigation_lease_seconds)
    with factory() as db:
        jobs = db.scalars(
            select(InvestigationRequest)
            .where(
                or_(
                    InvestigationRequest.status == "queued",
                    (InvestigationRequest.status == "collecting")
                    & (InvestigationRequest.claimed_at < cutoff),
                )
            )
            .order_by(InvestigationRequest.created_at, InvestigationRequest.id)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            incident = db.scalar(
                select(Incident)
                .where(Incident.id == job.incident_id)
                .with_for_update(skip_locked=True)
            )
            if incident is None:
                continue
            other = db.scalar(
                select(InvestigationRequest.id).where(
                    InvestigationRequest.incident_id == incident.id,
                    InvestigationRequest.id != job.id,
                    InvestigationRequest.status == "collecting",
                    InvestigationRequest.claimed_at >= cutoff,
                )
            )
            if other:
                continue
            for previous in db.scalars(
                select(Investigation).where(
                    Investigation.request_id == job.id, Investigation.status == "collecting"
                )
            ):
                previous.status, previous.summary = (
                    "failed",
                    "Read-only worker lease expired; retained evidence preserved",
                )
            if job.attempts >= 3:
                job.status, job.finished_at = "failed", stamp
                audit(
                    db,
                    "incident",
                    incident.id,
                    "collection_attempts_exhausted",
                    {"request_id": str(job.id)},
                    "investigation-worker",
                )
                db.commit()
                return None
            token, run_id = str(uuid4()), uuid4()
            job.status, job.claimed_at, job.claim_token = "collecting", stamp, token
            job.attempts += 1
            db.add(
                Investigation(
                    id=run_id,
                    incident_id=incident.id,
                    request_id=job.id,
                    provider="mcp",
                    mode="live",
                    status="collecting",
                    summary="Collecting live evidence",
                    result={"stage": "collecting"},
                )
            )
            audit(
                db,
                "incident",
                incident.id,
                "collection_started",
                {
                    "request_id": str(job.id),
                    "investigation_id": str(run_id),
                    "attempt": job.attempts,
                },
                "investigation-worker",
            )
            result = {
                "job_id": job.id,
                "token": token,
                "run_id": run_id,
                "incident_id": incident.id,
                "target_uid": incident.target_uid,
            }
            db.commit()
            return result
    return None


def owned(db, work):
    job = db.scalar(
        select(InvestigationRequest)
        .where(InvestigationRequest.id == work["job_id"])
        .with_for_update()
    )
    if job is None or job.status != "collecting" or job.claim_token != work["token"]:
        return None
    if (
        datetime.now(timezone.utc) - utc(job.claimed_at)
    ).total_seconds() > settings.investigation_lease_seconds:
        return None
    return job


def save(factory, work, source, payload):
    with factory() as db:
        if owned(db, work) is None:
            return False
        identifier = uuid5(work["run_id"], source)
        if db.get(EvidenceItem, identifier) is not None:
            return True
        canonical = {
            key: (value.isoformat() if isinstance(value, datetime) else value)
            for key, value in payload.items()
        }
        db.add(
            EvidenceItem(
                id=identifier,
                investigation_id=work["run_id"],
                content_hash=digest(canonical),
                **payload,
            )
        )
        db.commit()
    return True


def run_once(factory=SessionLocal, reader=None):
    reader = reader or LiveReader()
    work = claim(factory)
    if work is None:
        return False
    scope_verified = False
    for source in TOOLS:
        try:
            if source != "kubernetes:deployment" and not scope_verified:
                raise ValueError("Target identity was not verified")
            payload = reader.collect(source, work["target_uid"])
            if source == "kubernetes:deployment":
                scope_verified = True
        except Exception:
            payload = {
                "source": source,
                "observed_at": datetime.now(timezone.utc),
                "fact": "Evidence source unavailable; no observation retained",
                "raw_data": {},
                "transport_id": None,
                "transport_hash": None,
                "target_uid": work["target_uid"],
                "mode": "live",
                "trust_label": "untrusted",
                "redacted": True,
                "collection_error": "Source unavailable or evidence validation failed",
            }
        if not save(factory, work, source, payload):
            return True
    with factory() as db:
        if owned(db, work) is None:
            return True
        evidence = db.scalars(
            select(EvidenceItem).where(EvidenceItem.investigation_id == work["run_id"])
        ).all()
        gaps = [item.source for item in evidence if item.collection_error]
        available = {item.source: item for item in evidence if not item.collection_error}
        sufficient = {"prometheus", "kubernetes:deployment", "direct:probe"} <= available.keys()
        assessment = "inconclusive"
        if sufficient:
            metrics = available["prometheus"].raw_data
            total, errors = (
                float(metrics.get("total_requests", 0)),
                float(metrics.get("error_requests_5xx", 0)),
            )
            if (
                all(math.isfinite(v) for v in (total, errors))
                and total >= 20
                and 0 <= errors <= total
            ):
                assessment = "active" if errors / total > 0.20 else "not_confirmed"
        context = [
            {
                "id": str(item.id),
                "source": item.source,
                "observed_at": utc(item.observed_at).isoformat(),
                "fact": item.fact[:2000],
                "raw_data": {"excerpt": json.dumps(item.raw_data)[:6000]},
            }
            for item in evidence
            if not item.collection_error
        ]
    analysis = None
    if sufficient and settings.analysis_enabled:
        try:
            analysis = reader.analyze(work["incident_id"], work["target_uid"], context, gaps)
            analysis = AnalysisResult.model_validate(analysis).model_dump(mode="json")
            ids = {item["id"] for item in context}
            hypotheses = analysis["analysis"]["hypotheses"]
            if not hypotheses or any(
                not h["supporting_evidence_ids"]
                or not set(h["supporting_evidence_ids"] + h["contradicting_evidence_ids"]) <= ids
                for h in hypotheses
            ):
                raise ValueError("Invalid retained-evidence citations")
        except Exception:
            analysis = None
            gaps.append("model:analysis_unavailable")
    with factory() as db:
        job = owned(db, work)
        if job is None:
            return True
        run = db.get(Investigation, work["run_id"])
        incident = db.get(Incident, work["incident_id"])
        result = {
            "stage": "analyzed" if analysis else "evidence_collected",
            "assessment": assessment,
            "gaps": gaps,
            "analysis": analysis,
        }
        run.result = result
        run.status = "needs_review" if gaps or not sufficient else "completed"
        run.summary = (
            analysis["analysis"]["summary"]
            if analysis
            else "Live evidence retained; manual review required"
            if gaps
            else "Live evidence collected; diagnosis not requested"
        )
        if analysis:
            run.provider = analysis["provider"]
        job.status, job.finished_at = run.status, datetime.now(timezone.utc)
        incident.assessment = assessment
        audit(
            db,
            "incident",
            incident.id,
            "investigation_finished",
            {
                "request_id": str(job.id),
                "investigation_id": str(run.id),
                "status": run.status,
                "assessment": assessment,
                "sources": len(evidence),
                "gaps": gaps,
            },
            "investigation-worker",
        )
        db.commit()
    return True


def main():
    while True:
        try:
            if not run_once():
                time.sleep(2)
        except Exception as error:
            # Never log connection strings, credentials, raw logs or provider response bodies.
            print(json.dumps({"event": "worker_error", "kind": type(error).__name__}), flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
