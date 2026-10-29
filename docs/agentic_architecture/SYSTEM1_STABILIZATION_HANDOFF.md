# System-1 stabilization handoff

This handoff covers Jev/Laya provider selection and validation.

## Delivered behavior

- `SYSTEM1_PROVIDER` now selects exactly `policy`, `jev`, or `laya`; `policy` is the offline default.
- Jev is contacted only when selected and configured with a non-mock key.
- The compatible endpoint is contacted when selected directly, or as an explicitly enabled Jev
  fallback.
- Complete provider answers are validated for required fields, probability bounds, and choice enums.
  Invalid, partial, unavailable, or malformed responses fall back to deterministic policy.
- Trusted physical Prometheus and Kubernetes Deployment observations remain mandatory even if an
  external provider reports high sufficiency.
- An advisory risk answer can never remove the explicit human-approval requirement.
- The SDK score shape is normalized before validation.
- The bundled `infra/laya` service is identified as a deterministic protocol fixture. It does not
  claim to run the Laya model.

## Local verification

| Check | Result |
|---|---|
| `python -m pytest -q apps/ai/tests` | 31 passed; one pre-existing LangGraph deprecation warning |
| `python -m pytest -q apps/ai/tests/test_laya.py` | 10 passed |
| `python -m compileall -q apps/ai/app apps/ai/tests infra/laya` | Passed |
| `git diff --check` for System-1-owned files | Passed |
| `docker compose config --quiet` | Passed; Docker reported a user-level config-file access warning |
| Local fixture `GET /health` | `200`, provider `deterministic-policy-compatibility` |
| Local fixture `POST /v1/systemone` | `200`, returned the expected bounded answer map |

The focused Docker check image build was attempted but the local Docker builder stopped producing
progress during its base-image user-creation layer, before tests ran. It was interrupted after the
direct locked-environment test suite passed. Container construction remains a separate CI or host
recheck; no container-test failure was observed.

## Boundaries

These checks do not establish live TypeSafe Jev behavior, a real Laya model deployment, diagnosis
quality, authenticated API integration, or infrastructure recovery. The decision engine remains
read-only and advisory.
