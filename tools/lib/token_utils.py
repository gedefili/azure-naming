"""JWT and Azure token utilities for local testing.

Provides functions to decode JWT tokens, format timestamps, and extract
tokens from Azure CLI output. Used by authentication and token management tools.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import jwt


def decode_jwt_claims(token: str) -> dict[str, Any]:
    """Decode JWT and return claims dictionary.

    Extracts the payload section of the JWT, base64-decodes it,
    and returns the JSON claims dict.

    Args:
        token: JWT token string (format: header.payload.signature)

    Returns:
        Decoded claims dictionary from the JWT payload

    Raises:
        ValueError: If token format is invalid
        json.JSONDecodeError: If payload is not valid JSON
    """
    try:
        header, payload, _ = token.split(".")
    except ValueError as e:
        raise ValueError(f"Invalid JWT format (expected 3 parts, got {len(token.split('.'))})")  from e

    decoded = jwt.api_jws.base64url_decode(payload.encode())
    return json.loads(decoded)


def format_expiry_timestamp(timestamp: str | None) -> str:
    """Convert ISO 8601 timestamp to local timezone string.

    Azure CLI returns timestamps like "2025-10-29T14:30:00.000000+00:00"
    or sometimes without timezone info. This converts to local time
    and returns ISO format string.

    Args:
        timestamp: ISO 8601 timestamp string (or None)

    Returns:
        Formatted timestamp in local timezone, or "unknown" if None
    """
    if not timestamp:
        return "unknown"
    try:
        # Azure CLI returns ISO 8601 without timezone, interpret as UTC
        dt = datetime.fromisoformat(timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().isoformat()
    except ValueError:
        return timestamp


def extract_token_from_cli_output(output: str) -> str | None:
    """Parse bearer token from script output.

    The output contains the token between markers:
    "=== Bearer Token ===\n<token>\n=== End Token ==="

    Args:
        output: Stdout from token retrieval script

    Returns:
        Token string if found, None otherwise
    """
    start_marker = "=== Bearer Token ==="
    end_marker = "=== End Token ==="
    
    start = output.find(start_marker)
    end = output.find(end_marker)
    
    if start == -1 or end == -1:
        return None
    
    # Extract line after start marker
    lines = output[start:end].splitlines()
    if len(lines) > 1:
        return lines[1].strip()
    
    return None
