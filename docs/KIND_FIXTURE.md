# Local kind incident fixture

This fixture implements the observable workload for Phase 1. It does not create
an API incident, collect MCP evidence, approve a proposal, or restore a workload
through FixProof. The `reset` command is a developer operation using local
baseline state; the AI/MCP restore action remains disabled.

## Prerequisites and topology

- Docker Desktop with Linux containers, `kubectl`, Python 3.12+, and `kind`
  v0.27.0 or newer. The cluster uses the Kubernetes v1.32.2 kind node image
  pinned by digest in `infra/kind/cluster.yaml`.
- Copy `.env.example` to ignored `.env` and set the local database and Grafana
  passwords. The Groq key is not needed for the workload test.
- `kind` maps its node port 30080 to host port 18080. `sample-api` has one pod
  and a NodePort Service; `sample-traffic` sends about one work request per
  second to the Service from inside `fixproof-demo`. Port 18080 currently binds
  all host interfaces to make the Docker Desktop container-to-host path work;
  use this fixture only on a trusted local network.
- Compose Prometheus scrapes `host.docker.internal:18080/metrics`. Compose adds
  `host.docker.internal:host-gateway` for Linux Docker Engine. A successful
  `up{job="fixproof-sample"}` is the container-side connectivity check; a host
  `curl` alone does not establish that scrape path.

The sample endpoints are `/readyz` (process readiness), `/healthz` (functional
health), `/api/work` (user traffic), and `/metrics` (request counters labeled by
route and status class). `FAIL_MODE=on` makes health and work return 500 while
readiness remains 200. The injected value lives in a new Deployment pod
template, producing a new revision.

## Run it

From the repository root:

```powershell
docker compose up --build --wait --wait-timeout 180
python scripts/smoke.py
python scripts/kind_demo.py cycle
```

`cycle` creates or reuses the `fixproof` cluster, builds and loads the sample
image, applies the manifests, captures the healthy Deployment template, then
runs two fault/reset cycles. It waits 70 seconds per metric window. Each fault
window must contain at least 20 `/api/work` requests and more than 20% 5xx.
Each healthy window must contain at least 20 requests and less than 1% 5xx.
Prometheus must report `up=1`; readiness and functional health must match the
expected phase. The command prints observed revision, counts, ratio, and time,
and saves passing observations to ignored `.local/kind_acceptance.json`.

For manual inspection instead:

```powershell
python scripts/kind_demo.py bootstrap
python scripts/kind_demo.py fault
Start-Sleep -Seconds 70
python scripts/kind_demo.py verify --phase fault
python scripts/kind_demo.py reset
Start-Sleep -Seconds 70
python scripts/kind_demo.py verify --phase healthy
```

Bootstrap stores the exact healthy pod template, its SHA-256 hash, Deployment
UID, revision, and capture time in ignored `.local/kind_baseline.json`. It
refuses to capture a Deployment with active `FAIL_MODE`. Fault injection is
allowed only when the current template matches that baseline. Reset restores
the saved template and checks its hash, rather than taking the desired state
from an LLM response. A changed UID requires a new healthy bootstrap.

To stop the stack while retaining its database, run `docker compose down`.
To delete the demo cluster, run `kind delete cluster --name fixproof`; this
deletes the cluster and its workloads. After deletion, bootstrap captures a
new baseline for the new Deployment UID. Do not use `docker compose down -v`
unless you intend to delete the application database volume.

## Groq during development

The ignored `.env` should contain:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=<your Groq key>
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=openai/gpt-oss-20b
```

Do not put a Groq key under `NEBIUS_API_KEY`; that variable selects the Nebius
endpoint only. Set `LLM_PROVIDER=nebius` and supply a real `NEBIUS_API_KEY`
when moving to Nebius. The AI service's analysis and chat share the provider
selection. Missing or mock credentials, unsupported providers, transport
errors, and uncited responses leave live analysis unavailable or
`needs_review`; synthetic analysis is still an explicit request mode only.

This provider switch does not complete Phase 4. The current model response
parser still turns cited prose into one fixed-confidence hypothesis, and the
AI graph still ends with no executable proposal. Real MCP evidence and a strict
structured model response are later gates.

## Verification recorded on 2026-10-26

- Sample HTTP behavior: one local unit test passed.
- AI provider/guardrail tests: nine passed in the cached AI checks image.
- Focused Ruff checks and `docker compose config --quiet` passed.
- With a temporary host sample server on port 18080, the Compose Prometheus
  container reported `up{job="fixproof-sample"}=1`. This proves its scrape
  path to the host port, not the kind Service behind that port.
- The cached Grafana image returned `database: ok` at `/api/health` on local
  port 3300, which is used because another local service owns port 3000.
- One minimal live Groq completion with `openai/gpt-oss-20b` passed from the
  host. A second live call through `get_nemotron_llm()` in the cached AI
  checks container passed, verifying the selected provider and container
  outbound path. Neither call was an evidence-backed investigation.
- `docker compose up --build --wait --wait-timeout 180` failed while Docker
  resolved `ghcr.io` for the pinned uv build image. Pulling the pinned kind
  node image separately failed because Docker could not resolve
  `registry-1.docker.io`. No full-stack smoke or kind cycle result is claimed.
  Retry both commands once Docker Desktop registry DNS works; do not mark
  Phase 0 or Phase 1 complete until their exit gates pass.
- A `--no-build` core-stack attempt reached Grafana after moving its occupied
  host port from 3000 to 3300. The cached API image then failed startup because
  it lacks `alembic/env.py`; the current API Dockerfile does copy that file.
  The cached image is stale and cannot establish a source-build smoke pass.
