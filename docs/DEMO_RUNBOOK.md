# Demo runbook

1. `copy .env.example .env`, then `make up`, `make migrate`, and `make seed`.
2. Open the Overview and Incidents pages. The seeded incident is clearly a local deterministic demo.
3. Call `POST /api/v1/incidents/{id}/investigate` in API docs to generate a mock-labelled recommendation; approve it with the exact ID.
4. Inspect `/api/v1/audit-events` and the Cost Autopsy card. It separates measured October total ($2,450) from estimated savings ($450) and exposes the capacity-reduction assumption.
5. Do not claim execution or recovery: execution/verification adapters are intentionally a subsequent implementation phase.
