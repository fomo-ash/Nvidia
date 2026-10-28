# FixProof AI service

This service runs the advisory investigation graph. It collects bounded evidence through MCP,
checks whether required source types are present, asks the configured model for causal analysis,
and returns a `needs_review` result. It has no infrastructure mutation authority.

## System-1 provider selection

`SYSTEM1_PROVIDER` is an explicit selector:

| Value | Behavior |
|---|---|
| `policy` | Default. Makes no outbound System-1 request and checks for trusted live Prometheus and Kubernetes Deployment evidence. |
| `jev` | Calls TypeSafe Jev only when a non-mock key is configured. If `LAYA_ENABLED=true`, it may next try the compatible HTTP endpoint; otherwise it falls back to policy. |
| `laya` | Calls `LAYA_BASE_URL/v1/systemone`, validates the complete response, and falls back to policy on any transport or schema failure. |

The Compose service named `laya` is a deterministic development compatibility server. It implements
the request/response protocol but does not package or run the Laya open-weights model. Point
`LAYA_BASE_URL` at a separately operated model service to use a real compatible deployment.

All remote answers are advisory. The engine validates probability ranges and choice enums, requires
trusted physical evidence even when a provider reports high sufficiency, and always preserves the
human-approval requirement for remediation.

## Configuration

```env
SYSTEM1_PROVIDER=policy

# Optional Jev provider
JEV_API_KEY=
TYPESAFE_BASE_URL=https://api.typesafe.ai

# Compatible endpoint, selected directly or as a Jev fallback
LAYA_ENABLED=false
LAYA_BASE_URL=http://laya:8000
LAYA_API_KEY=
```

## Focused verification

From the repository root:

```powershell
docker compose -f compose.checks.yaml run --build --rm ai-checks
docker compose build ai laya
docker compose up -d laya
Invoke-RestMethod http://localhost:8003/health
```

The health response identifies the bundled service as
`deterministic-policy-compatibility`. Stop it with `docker compose stop laya`.
