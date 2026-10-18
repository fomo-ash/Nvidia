# Demo runbook

This runbook demonstrates the current synthetic foundation. It does not demonstrate infrastructure execution or recovery.

1. Copy .env.example to .env if needed. Run `docker compose up --build --wait --wait-timeout 180`, then `docker compose run --rm api python -m app.seed`.
2. Open the console at http://localhost:5173 and API docs at http://localhost:8000/docs.
3. List incidents and select the seeded incident. Its evidence is empty before investigation.
4. Call POST /api/v1/incidents/{id}/investigate. Review action, target, parameters, retained synthetic evidence, version, expiry, and proposal_hash.
5. Approve the exact recommendation using POST /api/v1/recommendations/{id}/approve with `{"proposal_hash":"<returned digest>"}`. The current demo records local-demo-user; it does not authenticate an operator.
6. Repeat approval and confirm 409. Reinvestigate the incident: version increments, the old record becomes superseded, and a fresh digest must be reviewed.
7. Inspect the incident timeline and audit list. Entries represent actual API decisions rather than a fabricated recovery.
8. Inspect the sample Cost Autopsy: October total $2,450, September $1,200, increase $1,250 (104.17%). Compute contributes $900 of the increase; storage contributes $350. Estimated savings are $525 = $2,100 eligible compute cost × 25%, assuming cost scales with capacity and health remains acceptable.
9. Open Grafana's FixProof API foundation dashboard. It shows API-process scrape health and memory, not incident recovery metrics.
10. Run `python scripts/smoke.py` for the automated HTTP equivalent (it creates its own synthetic incident). Stop with `docker compose down`; data is retained.

The next real demo must introduce a monitored workload fault, gather attributable evidence, test a bounded fix where practical, obtain approval, execute through a controlled adapter, and retain independent before/after measurements. Failed tests and verification must remain visible.
