# File: sanmar_naming/utils/auth.py
# Version: 1.1.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Shared utility for authenticating and authorizing users via Entra ID claims from EasyAuth.

import base64
import json
import logging
from typing import List, Dict

# Define known group IDs for Entra roles (replace with real GUIDs from Entra)
ROLE_GROUPS = {
    "admin": "<entra-group-id-for-admins>",
    "manager": "<entra-group-id-for-managers>",
    "user": "<entra-group-id-for-users>"
}

# Decode and parse the EasyAuth client principal
def parse_client_principal(headers: Dict[str, str]) -> dict:
    encoded = headers.get("x-ms-client-principal")
    if not encoded:
        raise ValueError("Missing client principal header (x-ms-client-principal)")

    decoded = base64.b64decode(encoded)
    principal_json = json.loads(decoded)
    logging.debug(f"[auth] Parsed principal: {principal_json}")
    return principal_json

# Extract user ID from client principal
def get_user_id(principal: dict) -> str:
    for claim in principal.get("claims", []):
        if claim.get("typ") == "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier":
            return claim.get("val")
    return ""

# Check if user is in any known role
def get_user_roles(principal: dict) -> List[str]:
    roles = []
    groups = [claim["val"] for claim in principal.get("claims", []) if claim.get("typ") == "groups"]
    for role, group_id in ROLE_GROUPS.items():
        if group_id in groups:
            roles.append(role)
    return roles

# Require basic user access to hit endpoint
def is_authenticated_user(user_roles: List[str]) -> bool:
    return "user" in user_roles or "manager" in user_roles or "admin" in user_roles

# Check if user has access to a resource
# User must be admin/manager OR directly involved
# Used in individual name audit

def is_authorized(user_roles: List[str], user_id: str, claimed_by: str, released_by: str) -> bool:
    if "admin" in user_roles or "manager" in user_roles:
        return True
    return user_id.lower() in [
        (claimed_by or "").lower(),
        (released_by or "").lower()
    ]
