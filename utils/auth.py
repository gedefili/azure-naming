# File: sanmar_naming/utils/auth.py
# Version: 1.1.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Shared utility for authenticating and authorizing users via Entra ID claims from EasyAuth.

import base64
import json
import logging
import os
from typing import Dict, List

import jwt
from jwt import PyJWKClient, InvalidTokenError

def _load_role_groups() -> Dict[str, str]:
    """Load Entra group IDs for roles from environment variables."""

    groups: Dict[str, str] = {}
    for role in ROLE_HIERARCHY:
        env_var = f"AZURE_ROLE_GROUP_{role.upper()}"
        group_id = os.environ.get(env_var)
        if group_id:
            groups[role] = group_id
        else:
            logging.debug("[auth] Role group env var %s not set", env_var)
    return groups

# JWKS endpoint for validating JWTs
TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
JWKS_URL = (
    f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    if TENANT_ID
    else ""
)

ROLE_HIERARCHY = ["user", "manager", "admin"]
ROLE_GROUPS = _load_role_groups()


class AuthError(Exception):
    """Raised when authentication or authorization fails."""

    def __init__(self, message: str, status: int = 401) -> None:
        super().__init__(message)
        self.status = status

# Decode and parse the EasyAuth client principal
def parse_client_principal(headers: Dict[str, str]) -> dict:
    encoded = headers.get("x-ms-client-principal")
    if not encoded:
        raise ValueError("Missing client principal header (x-ms-client-principal)")

    decoded = base64.b64decode(encoded)
    principal_json = json.loads(decoded)
    logging.debug(f"[auth] Parsed principal: {principal_json}")
    return principal_json


def verify_jwt(headers: Dict[str, str]) -> dict:
    """Validate Authorization bearer token and return claims."""
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthError("Missing bearer token", status=401)

    token = auth_header.split(" ", 1)[1]

    if not JWKS_URL:
        raise AuthError("Tenant ID not configured", status=500)

    jwk_client = PyJWKClient(JWKS_URL)
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID or None,
        )
        logging.debug(f"[auth] Verified JWT claims: {claims}")
        return claims
    except (InvalidTokenError, Exception) as exc:
        logging.exception("[auth] JWT validation failed")
        raise AuthError("Invalid token", status=401) from exc


def require_role(headers: Dict[str, str], min_role: str = "user") -> (str, List[str]):
    """Verify JWT and ensure the caller has at least the given role."""

    claims = verify_jwt(headers)
    roles = claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]

    if min_role not in ROLE_HIERARCHY:
        raise AuthError("Invalid role configuration", status=500)

    allowed_roles = ROLE_HIERARCHY[ROLE_HIERARCHY.index(min_role) :]
    if not set(roles).intersection(allowed_roles):
        raise AuthError("Forbidden", status=403)

    return claims.get("oid", ""), roles

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
