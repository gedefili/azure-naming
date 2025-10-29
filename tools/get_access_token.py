"""Utility to obtain a bearer token for local testing.

This script wraps the Azure CLI `az account get-access-token` command and
returns the raw token so it can be pasted into curl/Postman, along with a
summary of the decoded claims.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# Support both running from workspace root and tools directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.lib import decode_jwt_claims, extract_token_from_cli_output, format_expiry_timestamp, run_az_command


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch an Azure access token for local testing.")
    parser.add_argument(
        "--client-id",
        default=os.environ.get("AZURE_CLIENT_ID"),
        help="Application (client) ID for the Azure AD app. Defaults to $AZURE_CLIENT_ID.",
    )
    parser.add_argument(
        "--resource",
        help="Resource identifier to request (defaults to api://<client-id>).",
    )
    parser.add_argument(
        "--scope",
        help="Optional OAuth scope to request instead of --resource (e.g. api://<client-id>/.default).",
    )
    parser.add_argument(
        "--show-claims",
        action="store_true",
        help="Print decoded JWT claims in addition to the raw token.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = get_parser()
    args = parser.parse_args(argv)

    if not args.client_id and not args.resource and not args.scope:
        parser.error("Provide --client-id or explicitly set --resource/--scope.")

    if args.scope and args.resource:
        parser.error("Specify either --resource or --scope, not both.")

    resource = args.resource
    if not resource and not args.scope:
        resource = f"api://{args.client_id}"

    az_args: list[str] = ["account", "get-access-token"]
    if args.scope:
        az_args.extend(["--scope", args.scope])
    elif resource:
        az_args.extend(["--resource", resource])

    token_info = run_az_command(az_args)
    token = token_info.get("accessToken")
    if not token:
        raise RuntimeError("Azure CLI output did not include an accessToken field.")

    expires = format_expiry_timestamp(token_info.get("expiresOn") or token_info.get("expiresOn"))

    print("\n=== Bearer Token ===")
    print(token)
    print("=== End Token ===\n")
    print(f"Expires: {expires}")
    print(f"Tenant: {token_info.get('tenant') or token_info.get('tenantId')}")
    print(f"User:   {token_info.get('userId') or token_info.get('user')}")

    if args.show_claims:
        claims = decode_jwt_claims(token)
        wanted_keys = ("aud", "roles", "scp", "oid", "tid", "appid", "upn", "exp")
        filtered = {k: claims.get(k) for k in wanted_keys if k in claims}
        print("\nClaims snippet:")
        print(json.dumps(filtered or claims, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:  # pragma: no cover - user feedback
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
