"""Fresh, fixed-target post-action readings; no model or patch authority."""

import asyncio
from datetime import datetime, timedelta, timezone
import math

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.kubernetes import KubernetesClient
from app.adapters.prometheus import PrometheusClient
from app.adapters.probe import ProbeClient
from app.config import settings


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: str = Field(min_length=1, max_length=80)
    execution_id: str = Field(min_length=36, max_length=36)
    desired_good_template_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    after: datetime


def measurement(name, source, at, value, threshold, operator):
    return {
        "name": name, "source": source, "observed_at": at,
        "value": value, "threshold": threshold, "operator": operator,
    }


async def verify_recovery(request: VerifyRequest):
    after = request.after
    if after.tzinfo is None:
        raise ValueError("Action completion time must be timezone aware")
    after = after.astimezone(timezone.utc)
    if request.uid != settings.KUBERNETES_TARGET_UID or not -5 <= (datetime.now(timezone.utc) - after).total_seconds() <= 3600:
        raise ValueError("Verification target or action time is invalid")
    # A complete Prometheus minute must begin strictly after the patch.
    wait_seconds = max(0, 75 - (datetime.now(timezone.utc) - after).total_seconds())
    if wait_seconds:
        await asyncio.sleep(wait_seconds)
    readings = []
    details = {"after": after.isoformat(), "target_uid": request.uid, "execution_id": request.execution_id}
    try:
        deployment = await KubernetesClient().get_deployment_status()
    except Exception:
        return {"status": "inconclusive", "mode": "live", "measurements": [],
                "details": {**details, "reason": "Deployment observation unavailable"}}
    stamp = datetime.now(timezone.utc).isoformat()
    details.update({"revision": deployment.get("revision"),
                    "resource_version": deployment.get("resource_version"),
                    "replicas_desired": deployment.get("replicas_desired"),
                    "replicas_available": deployment.get("replicas_available")})
    if (deployment.get("uid") != request.uid
        or deployment.get("execution_id") != request.execution_id
        or deployment.get("template_hash") != request.desired_good_template_hash):
        return {"status": "inconclusive", "mode": "live", "measurements": [],
                "details": {**details, "reason": "Deployment target or template changed after action"}}
    desired = deployment.get("replicas_desired")
    available = deployment.get("replicas_available")
    if not isinstance(desired, int) or desired < 1 or not isinstance(available, int):
        return {"status": "inconclusive", "mode": "live", "measurements": [],
                "details": {**details, "reason": "Rollout counts unavailable"}}
    readings.append(measurement("rollout_available", "kubernetes:deployment", stamp,
                                available, desired, "gte"))
    probes = []
    for index in range(3):
        probe = await ProbeClient().check_endpoint(settings.SAMPLE_APP_HEALTH_URL)
        observed = datetime.now(timezone.utc).isoformat()
        status = probe.get("status_code", 0)
        probes.append({"status_code": status, "observed_at": observed})
        readings.append(measurement(f"health_probe_{index + 1}", "direct:probe", observed,
                                    status, 200, "eq"))
        if index < 2:
            await asyncio.sleep(2)
    details["probes"] = probes
    metrics = await PrometheusClient().get_traffic_metrics("1m")
    if metrics.get("error"):
        bad_probe = any(probe["status_code"] != 200 for probe in probes)
        return {"status": "failed" if available < desired or bad_probe else "inconclusive",
                "mode": "live", "measurements": readings,
                "details": {**details, "reason": "Prometheus reading unavailable", "metrics_error": metrics["error"]}}
    try:
        start = datetime.fromisoformat(metrics["window_start"])
        end = datetime.fromisoformat(metrics["window_end"])
        scrape = datetime.fromisoformat(metrics["sample_observed_at"])
        total = float(metrics["total_requests"])
        errors = float(metrics["error_requests_5xx"])
    except (KeyError, TypeError, ValueError):
        return {"status": "inconclusive", "mode": "live", "measurements": readings,
                "details": {**details, "reason": "Incomplete traffic measurements"}}
    details.update({"window_start": start.isoformat(), "window_end": end.isoformat(),
                    "last_scrape_at": scrape.isoformat(), "total_requests": total,
                    "error_requests_5xx": errors, "error_ratio": errors / total if total else None})
    if (
        start.tzinfo is None or end.tzinfo is None or scrape.tzinfo is None
        or start < after or end - start < timedelta(seconds=60)
        or not all(math.isfinite(number) for number in (total, errors))
        or total < 20 or errors < 0 or errors > total
        or not -5 <= (end - scrape).total_seconds() <= 30
    ):
        return {"status": "inconclusive", "mode": "live", "measurements": readings,
                "details": {**details, "reason": "Traffic window is stale or insufficient"}}
    observed = end.isoformat()
    readings.extend([
        measurement("work_requests", "prometheus", observed, total, 20, "gte"),
        measurement("http_5xx_ratio", "prometheus", observed, errors / total, 0.01, "lt"),
    ])
    passed = available >= desired and all(probe["status_code"] == 200 for probe in probes) and errors / total < 0.01
    return {"status": "passed" if passed else "failed", "mode": "live",
            "measurements": readings, "details": {**details, "reason": "All recovery thresholds passed" if passed else "Recovery threshold failed"}}
