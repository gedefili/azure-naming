"""Fetch or persist an access token into a local .env file.

This helper supports two workflows:

1. Save an already-issued bearer token passed via --token.
2. Request a token via Azure CLI and save it, if `az` is available.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Support both running from workspace root and tools directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.lib import decode_jwt_claims, format_expiry_timestamp, run_az_command


DEFAULT_FUNCTION_BASE_URL = "https://wus2-prd-fn-aznaming.azurewebsites.net"


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Save an Azure Naming API token into a local .env file.")
    parser.add_argument("--token", help="Existing bearer token to save.")
    parser.add_argument(
        "--tenant-id",
        help="Entra tenant ID. Used for Azure CLI token requests and saved into the .env file.",
    )
    parser.add_argument(
        "--api-client-id",
        help="API app registration client ID. Defaults to $AZURE_CLIENT_ID.",
    )
    parser.add_argument(
        "--test-client-id",
        help="Optional public client app ID to store in the .env file for non-Azure-CLI flows.",
    )
    parser.add_argument("--resource", help="Explicit resource identifier, usually api://<api-client-id>.")
    parser.add_argument("--scope", help="Optional scope to request instead of --resource.")
    parser.add_argument(
        "--function-base-url",
        help="Function host URL to store alongside the token.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Target env file path. Defaults to .env in the current working directory.",
    )
    parser.add_argument(
        "--show-claims",
        action="store_true",
        help="Print a small decoded-claims summary after saving the token.",
    )
    return parser


def _load_env(env_path: Path) -> tuple[list[str], dict[str, int]]:
    if not env_path.exists():
        return [], {}

    lines = env_path.read_text(encoding="utf-8").splitlines()
    indexes: dict[str, int] = {}
    for index, line in enumerate(lines):
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        indexes[key] = index
    return lines, indexes


def _read_env_values(env_path: Path) -> dict[str, str]:
    lines, _ = _load_env(env_path)
    values: dict[str, str] = {}
    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return values


def _upsert_env_values(env_path: Path, values: dict[str, str]) -> None:
    lines, indexes = _load_env(env_path)

    for key, value in values.items():
        rendered = f"{key}={value}"
        if key in indexes:
            lines[indexes[key]] = rendered
        else:
            lines.append(rendered)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fetch_token_via_az(
    *,
    tenant_id: str | None,
    api_client_id: str | None,
    resource: str | None,
    scope: str | None,
) -> tuple[str, str | None, str | None]:
    if scope and resource:
        raise RuntimeError("Specify either --scope or --resource, not both.")

    if not resource and not scope:
        if not api_client_id:
            raise RuntimeError("Provide --api-client-id, --resource, or --scope when --token is omitted.")
        resource = f"api://{api_client_id}"

    az_args: list[str] = ["account", "get-access-token"]
    if tenant_id:
        az_args.extend(["--tenant", tenant_id])
    if scope:
        az_args.extend(["--scope", scope])
    elif resource:
        az_args.extend(["--resource", resource])

    token_info = run_az_command(az_args)
    token = token_info.get("accessToken")
    if not token:
        raise RuntimeError("Azure CLI output did not include an accessToken field.")

    return token, token_info.get("tenant") or token_info.get("tenantId"), token_info.get("expiresOn")


def main(argv: list[str] | None = None) -> int:
    parser = get_parser()
    args = parser.parse_args(argv)

    env_path = Path(args.env_file).expanduser().resolve()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing_values = _read_env_values(env_path)

    function_base_url = (
        args.function_base_url
        or os.environ.get("FUNCTION_BASE_URL")
        or existing_values.get("FUNCTION_BASE_URL")
        or DEFAULT_FUNCTION_BASE_URL
    )
    tenant_id = args.tenant_id or os.environ.get("AZURE_TENANT_ID") or existing_values.get("AZURE_TENANT_ID")
    api_client_id = args.api_client_id or os.environ.get("AZURE_CLIENT_ID") or existing_values.get("AZURE_CLIENT_ID")
    test_client_id = args.test_client_id or os.environ.get("TEST_CLIENT_ID") or existing_values.get("TEST_CLIENT_ID")

    token = args.token or os.environ.get("ACCESS_TOKEN")
    expires_on: str | None = None

    if not token:
        token, tenant_id_from_az, expires_on = _fetch_token_via_az(
            tenant_id=tenant_id,
            api_client_id=api_client_id,
            resource=args.resource,
            scope=args.scope,
        )
        tenant_id = tenant_id or tenant_id_from_az

    values = {
        "FUNCTION_BASE_URL": function_base_url,
        "AZURE_TENANT_ID": tenant_id or "",
        "AZURE_CLIENT_ID": api_client_id or "",
        "TEST_CLIENT_ID": test_client_id or "",
        "ACCESS_TOKEN": token,
    }
    _upsert_env_values(env_path, values)

    print(f"Saved token data to {env_path}")
    if expires_on:
        print(f"Expires: {format_expiry_timestamp(expires_on)}")

    if args.show_claims:
        claims = decode_jwt_claims(token)
        wanted_keys = ("aud", "roles", "scp", "oid", "tid", "appid", "upn", "exp")
        print("Claims snippet:")
        for key in wanted_keys:
            if key in claims:
                print(f"  {key}: {claims[key]}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:  # pragma: no cover - user feedback
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)