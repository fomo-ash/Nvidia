# Incident detection and intake

**Requirement 1: FixProof must detect or accept an incident.** This is an implementation specification for the first kind-based workflow. It describes target behavior, not current behavior. Today `POST /api/v1/incidents` stores a title, severity, and summary; it has no target identity, detection, source record, deduplication, or evidence-based confirmation.

## Outcome and scope

An incident is a durable local record that says an operator or detector observed a possible problem with an identified workload. Creating it queues investigation; it does not establish root cause, authorize remediation, or prove that the symptom is still present.

For the first MVP, **manual intake is required**. The operator can report that the sample application is unhealthy from the UI or API. FixProof then collects evidence and determines whether the fault can be confirmed. **Automatic detection is an optional follow-on entry path** into the same incident service. It must not create a separate investigation or approval logic. Both paths persist trigger source and observation time.

The first supported target is the Deployment in the `fixproof-demo` namespace of the local kind cluster. The deliberately introduced configuration change is described in [Initial incident](INITIAL_INCIDENT.md). Other namespaces, clusters, arbitrary hostnames, and third-party alerts are outside this MVP.

## Manual intake

1. The operator selects the registered sample Deployment and enters a short symptom such as “sample requests return 5xx.” The UI shows the cluster, namespace, Deployment name, and the most recently observed target UID. The operator can add a note, but cannot supply a shell command, arbitrary PromQL, or a mutation target.
2. The browser sends a `POST /api/v1/incidents` request with an idempotency key. The API authenticates the local operator session, resolves the target from its allowlisted integration configuration, and rejects unknown or mismatched target IDs. It establishes `reported_at` on the server and records the reporter identity from the session, not a body field.
3. The API creates or finds the open incident for the same target and symptom fingerprint in one transaction. It appends a `manual` trigger record even if the incident already exists, unless this exact idempotency key was already processed. A duplicate request returns the original result without a second trigger or investigation.
4. The response gives the incident ID, `open` state, trigger ID, whether an existing incident was reused, and a link to its queued investigation. The collector begins work once the MCP evidence phase is installed. The UI initially says “reported, awaiting evidence collection” and changes to “collecting evidence” only when collection starts. It must not display “detected” or “confirmed” just because the operator submitted it.

The API accepts a bounded summary and optional note. It rejects empty input, excessively long text, unsupported target, malformed timestamp, and conflicting reuse of an idempotency key. User text is untrusted and is not forwarded to the model as an instruction.

## Optional Prometheus detector

A local API worker may evaluate an approved query every 15 seconds after the manual flow works. It reads Prometheus through the MCP read tool and never accepts model-generated PromQL. The detector uses the sample app's `sample_http_requests_total` counter for route `/api/work`, with `job="fixproof-sample"` and status-class labels. For a 60-second window, compute total requests and 5xx requests separately using `sum(increase(...[1m]))`, then divide errors by total. Prometheus documents `increase()` for counters and its handling of counter resets ([query functions](https://prometheus.io/docs/prometheus/3.12/querying/functions/)).

The first rule fires only when the window contains at least 20 requests and more than 20% are 5xx on two consecutive evaluations. It records the query version, evaluation time, window, total, errors, ratio, scrape freshness, and target identity. A missing series, stale scrape, query error, zero denominator, or too little traffic yields `insufficient_evidence`; it cannot produce a healthy or faulty assertion. A later Prometheus alerting rule could supply the same trigger, but Alertmanager and notifications are not needed for the first workflow. Prometheus supports rule evaluation and pending/firing states ([alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)).

When the rule fires, the detector calls the **same internal intake service** used by manual reports with `source=prometheus` and a deterministic key based on target, rule, and firing window. If an incident is already open for that target and symptom, append the metric trigger and reuse it. A new incident is created only when no matching open incident exists. A resolved or closed incident can be followed by a new one after a later fault.

## Identity, deduplication, and state

The incident target is a structured tuple: local cluster ID, namespace, resource kind, Deployment name, and Kubernetes UID. Use the UID to catch delete/recreate cases. The incident fingerprint combines target identity and symptom class (`http_5xx_spike`); free-form text is not part of it. Keep all received triggers, with source `manual` or `prometheus`, in time order so the operator can see what initiated the case and whether another report arrived later.

Use separate fields for lifecycle and evidence assessment:

| Field | Values for this MVP | Meaning |
|---|---|---|
| Incident lifecycle | `open`, `investigating`, `awaiting_approval`, `remediating`, `verifying`, `closed` | Where the operator workflow stands. Closing is explicit. |
| Symptom assessment | `unassessed`, `confirmed`, `not_reproduced`, `insufficient_evidence` | What current measurements support. Manual intake starts `unassessed`. |
| Trigger source | `manual`, `prometheus` | How each trigger entered FixProof. An incident may have both. |

The existing database has a single free-form `status`; add constrained fields through a migration rather than treating the old values as authoritative. A report can remain open with `not_reproduced` or `insufficient_evidence` while an operator inspects it. No intake path changes a recommendation's approval status.

## Proposed API shape

The final contract belongs in OpenAPI. A representative manual request is:

```json
{
  "target_id": "local-kind/fixproof-demo/sample-api",
  "symptom": "http_5xx_spike",
  "summary": "Sample application returns 5xx after a configuration change",
  "note": "Observed while running the fault scenario"
}
```

The authenticated caller sends `Idempotency-Key` separately. A new incident returns HTTP 201; reuse returns HTTP 200 with `reused: true`. The result includes `incident_id`, `trigger_id`, target UID, `trigger_source`, `reported_at`, lifecycle, symptom assessment, and investigation link. `GET /incidents/{id}` exposes these fields, and `GET /incidents/{id}/timeline` includes trigger records and later evidence assessment changes. Invalid body is 422, unknown target 404, target identity drift or idempotency-key conflict 409, and unavailable Kubernetes/Prometheus is surfaced as an integration error while preserving a valid manual report for later collection.

The detector uses an internal service call, not an unauthenticated public endpoint. If an external webhook is added later, it needs authentication, replay protection, a source allowlist, and its own adapter.

## Local persistence and audit

Extend `incidents` with target identity, fingerprint, lifecycle, assessment, first/last observed times, and current investigation ID. Add immutable `incident_triggers` with source, server receipt time, source observation time, reporter or rule ID, normalized measurements, payload hash, and idempotency key. Keep raw metric/query details as bounded local evidence with provenance. Index open incidents by fingerprint and make trigger idempotency keys unique. Intake, reuse, assessment changes, and failures create audit events. Retain the original trigger even if later evidence contradicts it.

The migration must preserve existing seeded incidents as labeled legacy demo data. Those rows have no verified target UID or trigger and cannot be silently promoted to real detected incidents.

## Operator experience

The incident list shows trigger source, target, first/last observation time, current assessment, and lifecycle. The detail page distinguishes “reported by operator” from “detected from Prometheus.” It shows the metric numerator, denominator, ratio, and evaluation window when detection is metric-based. While collection runs, it says “investigating”; if data is missing, it states which source failed and offers a retry. It never describes a manual report as a confirmed outage or an AI hypothesis as a measured fact.

## Acceptance tests

- Manual report for the allowlisted Deployment creates one open incident and one immutable trigger, queues investigation, and initially has `unassessed` assessment.
- Repeating the same idempotency key returns the same incident and trigger. A second report for the same open target/symptom reuses the incident and adds a distinct trigger.
- Unknown namespace, wrong Deployment UID, unsupported symptom, oversized note, and unauthenticated mutation are rejected without creating an incident.
- In the fault fixture, the Prometheus rule requires sufficient traffic and two evaluations; it attaches measurements to the open case or creates one if needed. A reset plus later new fault can create a new case after closure.
- Missing/stale metrics, low traffic, Prometheus timeout, and counter reset are handled without a false “healthy” or “confirmed” result.
- The UI labels manual and metric triggers accurately; source observation, server receipt, and evidence timestamps are visible and ordered.

This intake milestone is complete when a clean kind run can accept the sample app incident, preserve its source and target, queue investigation, and show an honest `unassessed` assessment. Phase 3 makes the queued investigation collect real evidence. Automatic detection is complete only after the optional rule, deduplication, and negative tests pass.
