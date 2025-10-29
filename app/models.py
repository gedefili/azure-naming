"""Pydantic models shared across HTTP routes."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class NameClaimRequest(BaseModel):
    """Schema describing the payload used to generate and claim a name."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    resource_type: str = Field(..., description="Azure resource type (e.g. storage_account).")
    region: str = Field(..., description="Azure region short code (e.g. wus2).")
    environment: str = Field(..., description="Deployment environment (e.g. dev, prod).")
    project: str | None = Field(default=None, description="Optional project or domain segment.")
    purpose: str | None = Field(default=None, description="Optional purpose or subdomain segment.")
    system: str | None = Field(default=None, description="Optional system identifier.")
    index: str | None = Field(default=None, description="Optional numeric tie breaker.")
    session_id: str | None = Field(
        default=None,
        description="Optional session identifier to apply user defaults.",
        alias="sessionId",
    )


class DisplayFieldEntry(BaseModel):
    key: str
    label: str
    value: str | None = None
    description: str | None = None


class NameClaimResponse(BaseModel):
    """Successful response when a name is generated and claimed."""

    name: str
    resourceType: str
    region: str
    environment: str
    slug: str
    claimedBy: str
    project: str | None = None
    purpose: str | None = None
    system: str | None = None
    index: str | None = None
    display: List[DisplayFieldEntry] = Field(default_factory=list)
    summary: str | None = Field(default=None, description="Human-readable summary produced by the naming rule template.")


class ReleaseRequest(BaseModel):
    """Schema describing a release request."""

    name: str = Field(..., description="Fully qualified name to release.")
    region: str | None = Field(default=None, description="Region where the name was registered (optional if resolvable from name).")
    environment: str | None = Field(default=None, description="Environment where the name was registered (optional if resolvable from name).")
    reason: str | None = Field(
        default="not specified",
        description="Optional note describing why the name is being released.",
    )


class MessageResponse(BaseModel):
    message: str


class SlugLookupResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    resourceType: str = Field(..., description="Canonical resource type used for slug resolution.")
    slug: str = Field(..., description="Resolved short code for the resource type.")
    fullName: str | None = Field(default=None, description="Human-readable label for the resource type, when available.")
    source: str | None = Field(default=None, description="Origin of the slug mapping (for example, azure_defined_specs).")
    updatedAt: str | None = Field(default=None, description="Timestamp of the most recent slug sync entry, when available.")


class AuditRecordResponse(BaseModel):
    name: str
    resource_type: str
    in_use: bool
    claimed_by: str | None = None
    claimed_at: str | None = None
    released_by: str | None = None
    released_at: str | None = None
    release_reason: str | None = None
    region: str
    environment: str
    slug: str | None = None
    project: str | None = None
    purpose: str | None = None
    system: str | None = None
    index: str | None = None


class AuditLogEntry(BaseModel):
    name: str
    event_id: str
    user: str | None = None
    action: str | None = None
    note: str | None = None
    timestamp: str
    region: str | None = None
    environment: str | None = None
    project: str | None = None
    purpose: str | None = None
    resource_type: str | None = None


class AuditBulkResponse(BaseModel):
    results: List[AuditLogEntry]
