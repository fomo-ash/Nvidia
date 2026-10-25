"""Pydantic schemas for MCP guarded execution actions."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class RestoreActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(default="fixproof-demo", min_length=1)
    deployment_name: str = Field(default="sample-api", min_length=1)
    expected_bad_template_hash: str = Field(
        ..., description="Hash of the current faulty pod template"
    )
    desired_good_template_hash: str = Field(
        ..., description="Hash of the trusted baseline pod template"
    )
    capability_token: str = Field(
        ..., description="Single-use signed authorization token from apps/api"
    )


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    details: dict[str, Any]
