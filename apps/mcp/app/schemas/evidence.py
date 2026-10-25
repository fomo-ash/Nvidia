"""Pydantic schemas for MCP telemetry evidence items."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"EVD-{uuid4().hex[:8]}")
    source: str = Field(
        ..., description="Telemetry source (e.g., prometheus, kubernetes:deployment, direct:probe)"
    )
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fact: str = Field(..., description="Human-readable fact summarizing the telemetry observation")
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Raw bounded telemetry payload"
    )
    content_hash: str = Field(default="")
    trusted: bool = Field(
        default=False, description="Whether data is untrusted log/event text or verified metric"
    )
    mode: Literal["live", "synthetic"] = "live"

    @field_validator("observed_at")
    @classmethod
    def aware_observation(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Evidence observation must include a timezone")
        return value.astimezone(timezone.utc)

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            canonical = json.dumps(
                {
                    "id": self.id,
                    "source": self.source,
                    "fact": self.fact,
                    "raw_data": self.raw_data,
                    "observed_at": self.observed_at.isoformat(),
                    "mode": self.mode,
                    "trusted": self.trusted,
                },
                sort_keys=True,
                default=str,
            )
            self.content_hash = hashlib.sha256(canonical.encode()).hexdigest()
