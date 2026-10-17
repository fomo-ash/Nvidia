# Architecture

FixProof is a modular monolith: React/Vite serves the operator UI; FastAPI owns domain rules and OpenAPI; PostgreSQL persists approved domain data; Prometheus/Grafana observe the API. The current demo integration is deterministic and local-only.

```mermaid
flowchart LR
  UI[React web] --> API[FastAPI /api/v1]
  API --> DB[(PostgreSQL)]
  Prometheus --> API
  Grafana --> Prometheus
  API --> Mock[Mock LLM / synthetic evidence]
```

```mermaid
sequenceDiagram
  participant O as Operator
  participant A as API
  participant W as Investigation workflow
  O->>A: investigate incident
  A->>W: normalize bounded evidence
  W-->>A: immutable proposal (mock or provider)
  O->>A: approve exact proposal version
  A->>A: validate status/action allowlist
  A-->>O: execution record, then independent verification
```

Trust boundary: UI and logs are untrusted inputs. The LLM can only receive normalized read-only evidence and return validated structured output; it never receives shell or infrastructure credentials. Real cloud/Kubernetes adapters, authentication, secret management, and isolated execution are deferred until Phases 5–8.
