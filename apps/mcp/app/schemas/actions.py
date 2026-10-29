"""Pydantic schemas for MCP guarded execution actions."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class RestoreActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(min_length=36, max_length=36)
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    namespace: str = Field(default="fixproof-demo", min_length=1)
    deployment: str = Field(default="sample-api", min_length=1)
    uid: str = Field(min_length=1, max_length=80)
    resource_version: str = Field(min_length=1, max_length=80)
    expected_bad_template_hash: str = Field(
        ..., pattern=r"^[a-f0-9]{64}$", description="Hash of the current faulty pod template"
    )
    desired_good_template_hash: str = Field(
        ..., pattern=r"^[a-f0-9]{64}$", description="Hash of the trusted baseline pod template"
    )
    desired_template: dict[str, Any]
    capability_token: str = Field(
        ..., description="Single-use signed authorization token from apps/api"
    )


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    details: dict[str, Any]
