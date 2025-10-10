"""Centralised imports for route dependencies."""

from __future__ import annotations

import logging
from typing import Iterable

try:  # pragma: no cover - optional dependency during docs builds
    from azure.data.tables import UpdateMode
except ImportError:  # pragma: no cover
    class UpdateMode:  # type: ignore[override]
        MERGE = "MERGE"

try:  # pragma: no cover - dependency may be optional in some environments
    from azure.core.exceptions import AzureError, ResourceNotFoundError
except ImportError:  # pragma: no cover - fallback when Azure SDK extras absent
    class AzureError(Exception):
        """Fallback AzureError when the Azure SDK is unavailable."""

    class ResourceNotFoundError(Exception):  # type: ignore[override]
        """Fallback ResourceNotFoundError when Azure SDK is absent."""

from adapters.audit_logs import write_audit_log
from adapters.slug_fetcher import SlugSourceError, get_all_remote_slugs
from adapters.storage import get_table_client
from core.auth import AuthError, is_authorized, require_role
from core.name_service import (
    InvalidRequestError,
    NameConflictError,
    NameGenerationResult,
    generate_and_claim_name,
)

__all__: Iterable[str] = (
    "AuthError",
    "AzureError",
    "InvalidRequestError",
    "NameConflictError",
    "NameGenerationResult",
    "ResourceNotFoundError",
    "SlugSourceError",
    "UpdateMode",
    "generate_and_claim_name",
    "get_all_remote_slugs",
    "get_table_client",
    "is_authorized",
    "logging",
    "require_role",
    "write_audit_log",
)
