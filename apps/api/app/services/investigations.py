"""Read-only deterministic investigation boundary; no infrastructure credentials or tools."""

from datetime import datetime, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.api import EvidenceOut


class DemoParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Literal["rolling"]
    reason: str = Field(min_length=1, max_length=2000)


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(pattern=r"^restart_demo_workload$")
    target: str = Field(pattern=r"^demo/api-workers$")
    parameters: DemoParameters
    evidence: list[EvidenceOut] = Field(min_length=1, max_length=20)


class InvestigationProvider(Protocol):
    def investigate(self) -> Proposal: ...


class MockInvestigationProvider:
    def investigate(self) -> Proposal:
        return Proposal(
            action="restart_demo_workload",
            target="demo/api-workers",
            parameters={
                "strategy": "rolling",
                "reason": "Synthetic elevated error rate; restart is a demo hypothesis, not a proven fix.",
            },
            evidence=[
                EvidenceOut(
                    source="demo-metrics",
                    observed_at=datetime.now(timezone.utc),
                    fact="Synthetic scenario: 5xx error rate is 18%.",
                )
            ],
        )
