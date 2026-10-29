"""FastAPI host for Anthropic MCP Server and HTTP endpoints."""

from fastapi import FastAPI
from pydantic import BaseModel, Field
from starlette.requests import Request
from mcp.server.sse import SseServerTransport

from app.config import settings
from app.schemas.evidence import EvidenceItem
from app.schemas.actions import ActionResult, RestoreActionRequest
from app.tools.patch import restore_known_good_template
from app.tools.verification import VerifyRequest, verify_recovery
from app.server import server
from app.tools import (
    check_service_health,
    get_deployment_status,
    get_pod_events,
    get_pod_logs,
    query_metrics,
)

app = FastAPI(
    title="FixProof MCP Server",
    description="Anthropic Model Context Protocol (MCP) server providing standardized, bounded Kubernetes & Prometheus telemetry.",
    version="0.1.0",
)

# Anthropic official SSE transport
sse = SseServerTransport("/messages/")


@app.get("/sse", tags=["MCP SSE"])
async def handle_sse(request: Request):
    """Anthropic official MCP Server-Sent Events (SSE) connection endpoint."""
    async with sse.connect_sse(request.scope, request.receive, request._send) as (
        read_stream,
        write_stream,
    ):
        await server.run(read_stream, write_stream, server.create_initialization_options())


app.mount("/messages/", sse.handle_post_message)


# Standard health check endpoint
@app.middleware("http")
async def service_auth(request, call_next):
    import hmac
    from fastapi.responses import JSONResponse
    from app.config import settings

    if request.url.path != "/health":
        key = settings.SERVICE_AUTH_TOKEN
        if len(key) < 32:
            return JSONResponse(
                {"detail": "Service authentication is not configured"}, status_code=503
            )
        if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + key):
            return JSONResponse({"detail": "Service authentication required"}, status_code=401)
    return await call_next(request)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "fixproof-mcp", "version": "0.1.0", "sdk": "anthropic-mcp"}


# Direct REST endpoints for HTTP callers / Dashboard queries
class QueryMetricsInput(BaseModel):
    window: str = Field(default="1m", description="PromQL increase window (e.g., '1m', '5m')")


class DeploymentStatusInput(BaseModel):
    namespace: str = Field(default="fixproof-demo")
    deployment_name: str = Field(default="sample-api")


class PodEventsInput(BaseModel):
    namespace: str = Field(default="fixproof-demo")
    limit: int = Field(default=20, ge=1, le=20)


class PodLogsInput(BaseModel):
    namespace: str = Field(default="fixproof-demo")
    deployment_name: str = Field(default="sample-api")
    lines: int = Field(default=100, ge=1, le=100)


class ServiceHealthInput(BaseModel):
    target_url: str = Field(default=settings.SAMPLE_APP_HEALTH_URL)


@app.post("/tools/query_metrics", response_model=EvidenceItem, tags=["REST Tools"])
async def handle_query_metrics(body: QueryMetricsInput | None = None) -> EvidenceItem:
    window = body.window if body else "1m"
    return await query_metrics(window=window)


@app.post("/tools/get_deployment_status", response_model=EvidenceItem, tags=["REST Tools"])
async def handle_deployment_status(body: DeploymentStatusInput | None = None) -> EvidenceItem:
    ns = body.namespace if body else "fixproof-demo"
    dep = body.deployment_name if body else "sample-api"
    return await get_deployment_status(namespace=ns, deployment_name=dep)


@app.post("/tools/get_pod_events", response_model=EvidenceItem, tags=["REST Tools"])
async def handle_pod_events(body: PodEventsInput | None = None) -> EvidenceItem:
    ns = body.namespace if body else "fixproof-demo"
    lim = body.limit if body else 20
    return await get_pod_events(namespace=ns, limit=lim)


@app.post("/tools/get_pod_logs", response_model=EvidenceItem, tags=["REST Tools"])
async def handle_pod_logs(body: PodLogsInput | None = None) -> EvidenceItem:
    ns = body.namespace if body else "fixproof-demo"
    dep = body.deployment_name if body else "sample-api"
    lines = body.lines if body else 100
    return await get_pod_logs(namespace=ns, deployment_name=dep, lines=lines)


@app.post("/tools/check_service_health", response_model=EvidenceItem, tags=["REST Tools"])
async def handle_service_health(body: ServiceHealthInput | None = None) -> EvidenceItem:
    url = body.target_url if body else settings.SAMPLE_APP_HEALTH_URL
    return await check_service_health(target_url=url)


@app.post(
    "/internal/restore_known_good_template", response_model=ActionResult, tags=["Internal Action"]
)
async def handle_restore(body: RestoreActionRequest) -> ActionResult:
    # Deliberately absent from the model-visible MCP tool registry.
    return await restore_known_good_template(body)


@app.post("/internal/verify_recovery", tags=["Internal Verification"])
async def handle_verify_recovery(body: VerifyRequest):
    return await verify_recovery(body)
