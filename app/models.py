"""Pydantic models shared across HTTP routes."""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


class NameClaimRequest(BaseModel):
    """Schema describing the payload used to generate and claim a name."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    resource_type: str = Field(..., description="Azure resource type (e.g. storage_account).")
    region: str = Field(..., description="Azure region short code (e.g. wus2).")
    environment: str = Field(..., description="Deployment environment (e.g. dev, prod).")
    project: str | None = Field(default=None, description="Optional project or domain segment.")
    purpose: str | None = Field(default=None, description="Optional purpose or subdomain segment.")
    subsystem: str | None = Field(default=None, description="Optional subsystem identifier.")
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
    subsystem: str | None = None
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


class AdminNameStateRequest(BaseModel):
    """Schema describing an admin remediation request for a claimed name."""

    name: str = Field(..., description="Fully qualified name to remediate.")
    action: str = Field(..., description="Admin action to apply: orphan or purge.")
    reason: str = Field(..., description="Required reason describing why the remediation is needed.")
    region: str | None = Field(default=None, description="Region where the name was registered (optional if resolvable from name).")
    environment: str | None = Field(default=None, description="Environment where the name was registered (optional if resolvable from name).")


class MessageResponse(BaseModel):
    message: str


class SlugLookupResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    resourceType: str = Field(..., description="Canonical resource type used for slug resolution.")
    slug: str = Field(..., description="Resolved short code for the resource type.")
    fullName: str | None = Field(default=None, description="Human-readable label for the resource type, when available.")
    source: str | None = Field(default=None, description="Origin of the slug mapping (for example, microsoft_caf).")
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
    claim_state: str | None = None
    state_changed_at: str | None = None
    state_changed_by: str | None = None
    state_version: int | None = None
    orphaned_by: str | None = None
    orphaned_at: str | None = None
    orphan_reason: str | None = None
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
    state_before: str | None = None
    state_after: str | None = None
    state_version: int | None = None


class AuditBulkResponse(BaseModel):
    results: List[AuditLogEntry]


class GrandfatherClaimRequest(BaseModel):
    """Payload used to reserve an existing Azure name as a grandfathered claim."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str = Field(..., description="Existing deployed Azure resource name to reserve.")
    resource_type: str = Field(
        ...,
        alias="resourceType",
        description="Canonical Azure Naming Service resource type.",
    )
    region: str = Field(..., description="Azure region short code such as wus2.")
    environment: str = Field(..., description="Environment short code such as dev or prd.")
    project: str | None = Field(default=None, description="Optional project or domain segment.")
    purpose: str | None = Field(default=None, description="Optional purpose segment.")
    subsystem: str | None = Field(default=None, description="Optional subsystem segment.")
    system: str | None = Field(default=None, description="Optional system identifier.")
    index: str | None = Field(default=None, description="Optional numeric or legacy differentiator.")
    claimed_by: str | None = Field(
        default=None,
        alias="claimedBy",
        description="Known current owner if available; null when unknown.",
    )
    ownership_status: Literal["identified", "unknown"] = Field(
        ...,
        alias="ownershipStatus",
        description="Whether a present-day owner is known.",
    )
    import_source: Literal["azure_inventory", "terraform_state", "manual", "manifest"] = Field(
        ...,
        alias="importSource",
        description="Where the adoption record came from.",
    )
    import_reference: str | None = Field(
        default=None,
        alias="importReference",
        description="Resource ID, manifest path, state address, or other evidence pointer.",
    )
    reason: str = Field(..., description="Why the name is being adopted now.")
    legacy_metadata: Dict[str, Any] | None = Field(
        default=None,
        alias="legacyMetadata",
        description="Optional non-authoritative legacy metadata captured for operators.",
    )


class GrandfatherClaimResponse(BaseModel):
    """Successful response when a name is adopted as a grandfathered claim."""

    name: str
    resourceType: str
    region: str
    environment: str
    grandfathered: bool = True
    complianceStatus: str
    ownershipStatus: str
    claimedBy: str | None = None
    importSource: str
    message: str


class ClaimReportEntry(BaseModel):
    """A single entry in the claims report."""

    name: str
    resourceType: str | None = None
    region: str | None = None
    environment: str | None = None
    claimState: str | None = None
    grandfathered: bool = False
    complianceStatus: str | None = None
    ownershipStatus: str | None = None
    claimedBy: str | None = None
    inUse: bool = False


class ClaimReportResponse(BaseModel):
    """Response for the claims report endpoint."""

    total: int
    results: List[ClaimReportEntry]
