# Team ownership and integration

The original four-member split remains a suggested coordination map, not a claim that those workstreams are complete. A solo developer can take the same interfaces in the [implementation order](IMPLEMENTATION_PLAN.md).

| Stream | Primary responsibility | Handoff |
|---|---|---|
| API and data | FastAPI, migrations, incident lifecycle, approval/execution policy, audit, verification decision | Publishes OpenAPI and state rules to UI and MCP streams. |
| Investigation | Evidence schema, Nebius Nemotron adapter, provider validation, citation checks, redaction | Consumes MCP read results; returns advisory validated output to API. |
| Local infrastructure | Compose, kind, sample app/fault, Prometheus, one MCP server, Kubernetes RBAC and allowed action | Proves container connectivity and tool behavior to API stream. |
| Operator UI | Incident evidence, proposal review, explicit approval, execution/verification timeline, integration status | Consumes versioned OpenAPI; never enforces the security gate alone. |

Review the contracts at three checkpoints: (1) evidence schema and sample metrics before inference work, (2) exact action/approval/preflight schema before any mutation is enabled, and (3) verification readings and status semantics before the final demo. Migration and action changes require safety and rollback notes. Keep the synthetic cost feature separately labeled and outside the first milestone.

| Phase | Primary stream | Required handoff |
|---|---|---|
| 0 Foundation confirmation | API + UI + local infrastructure | Preserve merged browser/API/check fixes and recheck full five-service smoke |
| 1 kind fault | Local infrastructure | Sample endpoints, metrics, and target identity |
| 2 Incident intake | API + UI | Trigger schema and authenticated operator flow |
| 3 MCP evidence | Local infrastructure + API | Bounded tool and evidence schemas |
| 4 Nemotron | Investigation | Validated response and evidence citations |
| 5 Approval | API + UI | Exact proposal hash and review screen |
| 6 Execution | API + local infrastructure | Preflight/action contract and Role permissions |
| 7 Verification | API + UI | Measured verdict and timeline |
| 8 Release | All streams | Clean-machine acceptance record |
