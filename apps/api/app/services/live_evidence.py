"""Authenticated bounded reads, envelope validation and redaction."""

from datetime import datetime, timezone
import hashlib
import json
import re
import urllib.request

from app.core.config import settings

TOOLS = {
    "kubernetes:deployment": ("get_deployment_status", {}),
    "prometheus": ("query_metrics", {"window": "1m"}),
    "kubernetes:events": ("get_pod_events", {"limit": 10}),
    "kubernetes:logs": ("get_pod_logs", {"lines": 50}),
    "direct:probe": ("check_service_health", {}),
}


def post(url, payload, *, timeout=10):
    if len(settings.service_auth_token) < 32:
        raise RuntimeError("Service authentication is not configured")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + settings.service_auth_token,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(65537)
    if len(body) > 65536:
        raise ValueError("Oversized service response")
    return json.loads(body)


def redact(value):
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if re.search(r"secret|token|password|authorization|api.?key", key, re.I)
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value[:100]]
    if isinstance(value, str):
        text = re.sub(r"(?i)(bearer\s+)[^\s\"',;]+", r"\1[REDACTED]", value)
        text = re.sub(
            r"(?i)((?:secret|password|token|api[_-]?key)\s*[=:]\s*)[^\s\"',;]+",
            r"\1[REDACTED]",
            text,
        )
        text = re.sub(r"\b(?:sk-|nvapi-)[A-Za-z0-9_-]{12,}", "[REDACTED]", text)
        return text[:8000]
    return value


def validate_envelope(data, source, target_uid):
    if not isinstance(data, dict) or len(json.dumps(data, allow_nan=False)) > 65536:
        raise ValueError("Invalid envelope")
    at = datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))
    if at.tzinfo is None:
        raise ValueError("Timezone required")
    at = at.astimezone(timezone.utc)
    if not -5 <= (datetime.now(timezone.utc) - at).total_seconds() <= 120:
        raise ValueError("Stale envelope")
    fields = {key: data[key] for key in ["id", "source", "fact", "raw_data", "mode", "trusted"]}
    fields["observed_at"] = at.isoformat()
    if data["source"] != source or data["mode"] != "live" or not isinstance(data["trusted"], bool):
        raise ValueError("Source or mode mismatch")
    if (
        not isinstance(data["raw_data"], dict)
        or not isinstance(data["fact"], str)
        or not 1 <= len(data["fact"]) <= 8000
        or not isinstance(data["id"], str)
        or not 1 <= len(data["id"]) <= 80
    ):
        raise ValueError("Malformed source payload")
    expected = hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()
    if data["content_hash"] != expected:
        raise ValueError("Envelope hash mismatch")
    if source == "kubernetes:deployment" and data["raw_data"].get("uid") != target_uid:
        raise ValueError("Deployment UID drift")
    return {
        "source": source,
        "observed_at": at,
        "fact": redact(data["fact"]),
        "raw_data": redact(data["raw_data"]),
        "transport_id": data["id"],
        "transport_hash": data["content_hash"],
        "target_uid": target_uid,
        "mode": "live",
        "trust_label": "untrusted",
        "redacted": True,
        "collection_error": None,
    }


class LiveReader:
    def collect(self, source, target_uid):
        tool, arguments = TOOLS[source]
        data = post(settings.mcp_server_url.rstrip("/") + "/tools/" + tool, arguments)
        return validate_envelope(data, source, target_uid)

    def analyze(self, incident_id, target_uid, evidence, gaps):
        return post(
            settings.ai_service_url.rstrip("/") + "/analyze",
            {
                "incident_id": str(incident_id),
                "target_uid": target_uid,
                "evidence": evidence,
                "gaps": gaps,
            },
            timeout=60,
        )
