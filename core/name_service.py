# File: core/name_service.py
# Version: 1.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Shared orchestrator for generating and claiming Azure-compliant names.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from adapters.audit_logs import write_audit_log
from adapters.storage import check_name_exists, claim_name
from core.name_generator import build_name
from core.naming_rules import NamingRule, load_naming_rule
from core.user_settings import settings_service
from core.validation import validate_name
from core.slug_service import get_slug

logger = logging.getLogger(__name__)


class InvalidRequestError(ValueError):
    """Raised when required fields are missing from a name generation payload."""


class NameConflictError(RuntimeError):
    """Raised when the generated name already exists in storage."""


@dataclass
class NameGenerationResult:
    name: str
    resource_type: str
    region: str
    environment: str
    slug: str
    rule: Optional[NamingRule] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "name": self.name,
            "resourceType": self.resource_type,
            "region": self.region,
            "environment": self.environment,
            "slug": self.slug,
        }
        # Include any additional metadata that was captured
        if self.metadata:
            for key, value in self.metadata.items():
                if key not in {"Slug", "RequestedBy"}:
                    # Convert CamelCase keys to camelCase for JSON response
                    json_key = key[0].lower() + key[1:] if key else key
                    payload[json_key] = value
        if self.rule and hasattr(self.rule, "render_display"):
            payload["display"] = self.rule.render_display(payload)
        if self.rule and hasattr(self.rule, "render_summary"):
            summary = self.rule.render_summary(payload)
            if summary:
                payload["summary"] = summary
        return payload


_REQUIRED_FIELDS = ("resource_type", "region", "environment")
_FIELD_ALIASES = {
    "system": "system_short",
    "system_short": "system_short",
    "subsystem": "subsystem",
    "index": "index",
}


def _normalise_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    normalised_payload = dict(payload)
    if "resourceType" in normalised_payload and "resource_type" not in normalised_payload:
        normalised_payload["resource_type"] = normalised_payload["resourceType"]

    missing = [field for field in _REQUIRED_FIELDS if not normalised_payload.get(field)]
    if missing:
        raise InvalidRequestError(
            f"Missing required field(s): {', '.join(missing)}"
        )

    optional_segments: Dict[str, str] = {}
    for source, target in _FIELD_ALIASES.items():
        value = normalised_payload.get(source)
        if value:
            optional_segments[target] = str(value).lower()

    return normalised_payload, optional_segments


def generate_and_claim_name(payload: Dict[str, Any], requested_by: str) -> NameGenerationResult:
    """Generate a compliant name from the payload and persist the claim."""

    session_id = payload.get("session_id") or payload.get("sessionId")
    scrubbed_payload = {k: v for k, v in payload.items() if k not in {"session_id", "sessionId"}}

    try:
        payload_with_defaults = settings_service.apply_defaults(
            scrubbed_payload,
            requested_by,
            session_id=session_id,
        )
    except Exception:  # pragma: no cover - defensive guard against external failures
        logger.exception(
            "Failed to load user settings defaults; proceeding with request payload only."
        )
        payload_with_defaults = dict(scrubbed_payload)

    normalized_payload, optional_segments = _normalise_payload(payload_with_defaults)

    resource_type = normalized_payload["resource_type"].lower()
    region = normalized_payload["region"].lower()
    environment = normalized_payload["environment"].lower()

    rule = load_naming_rule(resource_type)
    if hasattr(rule, "validate_payload"):
        try:
            rule.validate_payload({**normalized_payload})
        except ValueError as exc:
            raise InvalidRequestError(str(exc))

    slug = get_slug(resource_type)

    name = build_name(
        region=region,
        environment=environment,
        slug=slug,
        rule=rule,
        optional_inputs=optional_segments,
    )

    validate_name(name, rule)

    if check_name_exists(region, environment, name):
        raise NameConflictError(f"Name '{name}' is already in use.")

    subsystem_value = normalized_payload.get("subsystem")
    system_value = normalized_payload.get("system") or normalized_payload.get("system_short")
    index_value = normalized_payload.get("index")

    # Build entity metadata from all incoming fields
    # Include everything that was sent in the request, normalized to lowercase strings
    entity_metadata = {
        "Slug": slug,
        "Subsystem": str(subsystem_value).lower() if subsystem_value else None,
        "System": str(system_value).lower() if system_value else None,
        "Index": str(index_value).lower() if index_value else None,
        "RequestedBy": requested_by,
    }
    # Remove empty metadata values
    entity_metadata = {k: v for k, v in entity_metadata.items() if v}
    
    # Add any additional custom fields from the normalized payload
    # (excluding core naming fields and internal fields)
    core_fields = {"resource_type", "region", "environment", 
                   "system", "system_short", "subsystem", "index", "sessionId", "session_id"}
    skip_fields = {"sessionId", "session_id"}
    for key, value in normalized_payload.items():
        if key not in core_fields and key not in skip_fields and value is not None:
            # Normalize key names and values
            entity_key = key[0].upper() + key[1:] if key else key
            entity_value = str(value).lower() if isinstance(value, str) else value
            if entity_key not in entity_metadata:
                entity_metadata[entity_key] = entity_value

    claim_name(
        region=region,
        environment=environment,
        name=name,
        resource_type=resource_type,
        claimed_by=requested_by,
        metadata=entity_metadata,
    )

    # Build audit metadata from the entire incoming request payload
    # This ensures all metadata sent by the client is captured in the audit trail
    audit_metadata = {}
    
    # Add all incoming fields from the normalized payload (excluding internal/system fields)
    skip_fields = {"sessionId", "session_id"}
    for key, value in normalized_payload.items():
        if key not in skip_fields and value is not None:
            # Normalize key names to CamelCase for consistency
            if key == "resource_type":
                audit_metadata["ResourceType"] = str(value).lower()
            elif key == "region":
                audit_metadata["Region"] = str(value).lower()
            elif key == "environment":
                audit_metadata["Environment"] = str(value).lower()
            else:
                # For other fields, capitalize first letter
                audit_key = key[0].upper() + key[1:] if key else key
                audit_metadata[audit_key] = str(value).lower() if isinstance(value, str) else value
    
    # Always ensure core fields are present
    audit_metadata.setdefault("ResourceType", resource_type)
    audit_metadata.setdefault("Region", region)
    audit_metadata.setdefault("Environment", environment)
    audit_metadata["Slug"] = slug

    write_audit_log(
        name,
        requested_by,
        "claimed",
        note=f"{resource_type}:{region}-{environment}",
        metadata=audit_metadata,
    )

    return NameGenerationResult(
        name=name,
        resource_type=resource_type,
        region=region,
        environment=environment,
        slug=slug,
        metadata=entity_metadata,
        rule=rule,
    )
