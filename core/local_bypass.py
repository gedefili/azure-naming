# File: core/local_bypass.py
# Version: 1.0.0
# Created: 2026-03-12
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Local authentication bypass for development environments.
#
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECURITY-CRITICAL MODULE — READ BEFORE MODIFYING                  ║
# ║                                                                    ║
# ║  This module controls a complete authentication bypass.  When      ║
# ║  LOCAL_AUTH_BYPASS is active, ALL endpoints are accessible          ║
# ║  without a valid JWT, using the configured user ID and roles.      ║
# ║                                                                    ║
# ║  Safeguards:                                                       ║
# ║    1. A RuntimeError is raised at import time if the bypass is     ║
# ║       enabled while running in Azure (WEBSITE_INSTANCE_ID set).   ║
# ║    2. The bypass defaults to OFF — it requires an explicit env     ║
# ║       var  ALLOW_LOCAL_AUTH_BYPASS=true  to activate.              ║
# ║                                                                    ║
# ║  If either safeguard is weakened or removed, every protected       ║
# ║  endpoint becomes publicly accessible with elevated privileges.    ║
# ╚══════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

import logging
import os
from typing import Iterable, List, Optional

# ---------------------------------------------------------------------------
# Role helpers (duplicated intentionally so this module is self-contained and
# changes to auth.py role logic cannot silently alter bypass behaviour).
# ---------------------------------------------------------------------------

_ROLE_HIERARCHY = ["reader", "contributor", "admin"]

_ROLE_ALIASES = {
    "reader": "reader",
    "contributor": "contributor",
    "admin": "admin",
    "sanmar-naming-reader": "reader",
    "sanmar-naming-contributor": "contributor",
    "sanmar-naming-admin": "admin",
    "sanmar.naming.reader": "reader",
    "sanmar.naming.contributor": "contributor",
    "sanmar.naming.admin": "admin",
}


def _normalise_role_token(role: str) -> str:
    return (
        role.strip().lower().replace(" ", "-").replace("_", "-").replace(".", "-")
        if role
        else ""
    )


def _canonicalize_role(role: str) -> Optional[str]:
    token = _normalise_role_token(role)
    if not token:
        return None
    canonical = _ROLE_ALIASES.get(token, token)
    return canonical if canonical in _ROLE_HIERARCHY else None


def _canonicalize_roles(raw_roles: Iterable[str]) -> List[str]:
    seen: List[str] = []
    for role in raw_roles:
        canonical = _canonicalize_role(role)
        if canonical and canonical not in seen:
            seen.append(canonical)
    return seen


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"} if value else False


# ---------------------------------------------------------------------------
# Bypass configuration — evaluated once at import time
# ---------------------------------------------------------------------------

LOCAL_AUTH_BYPASS: bool = _to_bool(os.environ.get("ALLOW_LOCAL_AUTH_BYPASS", ""))

_IS_AZURE: bool = bool(os.environ.get("WEBSITE_INSTANCE_ID"))

if LOCAL_AUTH_BYPASS and _IS_AZURE:
    raise RuntimeError(
        "ALLOW_LOCAL_AUTH_BYPASS must not be enabled in Azure. "
        "Remove the environment variable from the Function App configuration."
    )

if LOCAL_AUTH_BYPASS:
    logging.warning(
        "[local_bypass] Local auth bypass is ACTIVE — local dev only"
    )

LOCAL_BYPASS_USER_ID: str = os.environ.get("LOCAL_BYPASS_USER_ID", "local-dev-user")

_LOCAL_BYPASS_RAW = [
    role.strip()
    for role in os.environ.get("LOCAL_BYPASS_ROLES", "contributor,admin").split(",")
    if role.strip()
]
LOCAL_BYPASS_ROLES: List[str] = _canonicalize_roles(_LOCAL_BYPASS_RAW) or ["contributor"]
