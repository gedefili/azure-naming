#!/usr/bin/env python3
"""Seed existing Azure resource names into the naming registry via the grandfather API.

This script reads a JSON manifest of existing resource names and calls
POST /api/claims/grandfather for each entry. It supports:

- Retry with exponential backoff on transient failures
- Idempotent re-adoption (200 responses treated as success)
- Dry-run mode for validation without API calls
- Structured result reporting with per-name status

Usage:
    # Against local Azurite stack (no auth required)
    python tools/seed_names.py manifest.json

    # Against production with bearer token
    python tools/seed_names.py manifest.json --endpoint https://wus2-prd-fn-aznaming.azurewebsites.net --token <JWT>

    # Acquire token automatically via Azure CLI
    python tools/seed_names.py manifest.json --endpoint https://wus2-prd-fn-aznaming.azurewebsites.net --az-login

    # Dry run (validate manifest only)
    python tools/seed_names.py manifest.json --dry-run

    # Generate a sample manifest
    python tools/seed_names.py --generate-sample > manifest.json

Manifest format:
    {
      "description": "Pilot seed manifest for azure-naming service concern",
      "claims": [
        {
          "name": "wus2-prd-rg-aznaming",
          "resource_type": "resource_group",
          "region": "wus2",
          "environment": "prd",
          "system": "aznaming",
          "ownership_status": "identified",
          "import_source": "terraform_state",
          "reason": "Grandfather existing resource before naming cutover"
        }
      ]
    }

Task: 461800 — Build seed and import workflow for existing Azure resource names
Story: 461799 — Cut over environs-iac naming to Azure Naming Service claims
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

LOCAL_ENDPOINT = "http://localhost:7071"
GRANDFATHER_PATH = "/api/claims/grandfather"

REQUIRED_FIELDS = {"name", "resource_type", "region", "environment", "ownership_status", "import_source", "reason"}
VALID_OWNERSHIP = {"identified", "unknown"}
VALID_IMPORT_SOURCE = {"azure_inventory", "terraform_state", "manual", "manifest"}

MAX_RETRIES = 3
INITIAL_BACKOFF_S = 1.0
BACKOFF_MULTIPLIER = 2.0

SAMPLE_MANIFEST: dict[str, Any] = {
    "description": "Sample seed manifest — edit claims to match your existing infrastructure",
    "claims": [
        {
            "name": "wus2-prd-rg-example",
            "resource_type": "resource_group",
            "region": "wus2",
            "environment": "prd",
            "system": "example",
            "ownership_status": "identified",
            "import_source": "terraform_state",
            "import_reference": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/wus2-prd-rg-example",
            "reason": "Grandfather existing resource before naming cutover",
            "claimed_by": "platform-team",
        },
        {
            "name": "wus2prdstexample",
            "resource_type": "storage_account",
            "region": "wus2",
            "environment": "prd",
            "system": "example",
            "ownership_status": "identified",
            "import_source": "terraform_state",
            "reason": "Grandfather existing storage account before naming cutover",
        },
    ],
}


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class SeedResult:
    name: str
    status: str  # "created", "exists", "conflict", "error"
    http_status: int | None = None
    message: str = ""


@dataclass
class SeedReport:
    total: int = 0
    created: int = 0
    exists: int = 0
    conflict: int = 0
    error: int = 0
    results: list[SeedResult] = field(default_factory=list)

    def add(self, result: SeedResult) -> None:
        self.total += 1
        self.results.append(result)
        if result.status == "created":
            self.created += 1
        elif result.status == "exists":
            self.exists += 1
        elif result.status == "conflict":
            self.conflict += 1
        else:
            self.error += 1


# ── Manifest validation ───────────────────────────────────────────────────

def validate_claim(claim: dict[str, Any], index: int) -> list[str]:
    """Validate a single claim entry. Returns a list of error messages."""
    errors: list[str] = []
    missing = REQUIRED_FIELDS - set(claim.keys())
    if missing:
        errors.append(f"claim[{index}]: missing required fields: {', '.join(sorted(missing))}")

    name = claim.get("name", "")
    if isinstance(name, str) and not name.strip():
        errors.append(f"claim[{index}]: 'name' must be a non-empty string")

    ownership = claim.get("ownership_status")
    if ownership and ownership not in VALID_OWNERSHIP:
        errors.append(f"claim[{index}]: 'ownership_status' must be one of {VALID_OWNERSHIP}, got '{ownership}'")

    import_src = claim.get("import_source")
    if import_src and import_src not in VALID_IMPORT_SOURCE:
        errors.append(f"claim[{index}]: 'import_source' must be one of {VALID_IMPORT_SOURCE}, got '{import_src}'")

    return errors


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate the full manifest structure. Returns a list of error messages."""
    errors: list[str] = []

    if not isinstance(manifest, dict):
        return ["Manifest must be a JSON object"]

    claims = manifest.get("claims")
    if not isinstance(claims, list):
        return ["Manifest must contain a 'claims' array"]

    if len(claims) == 0:
        errors.append("Manifest 'claims' array is empty")

    seen_names: set[str] = set()
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claim[{i}]: must be a JSON object")
            continue
        errors.extend(validate_claim(claim, i))
        name = claim.get("name", "")
        if name in seen_names:
            errors.append(f"claim[{i}]: duplicate name '{name}'")
        seen_names.add(name)

    return errors


# ── API interaction ────────────────────────────────────────────────────────

def build_request_body(claim: dict[str, Any]) -> dict[str, Any]:
    """Convert a manifest claim entry to the grandfather API request body."""
    body: dict[str, Any] = {}
    # Map snake_case fields to camelCase aliases where needed
    alias_map = {
        "resource_type": "resourceType",
        "claimed_by": "claimedBy",
        "ownership_status": "ownershipStatus",
        "import_source": "importSource",
        "import_reference": "importReference",
        "legacy_metadata": "legacyMetadata",
    }
    for key, value in claim.items():
        if value is None:
            continue
        wire_key = alias_map.get(key, key)
        body[wire_key] = value
    return body


def post_grandfather_claim(
    endpoint: str,
    claim: dict[str, Any],
    token: str | None,
    max_retries: int = MAX_RETRIES,
) -> SeedResult:
    """POST a single grandfather claim with retry logic."""
    import requests  # noqa: E402 — deferred import to keep startup fast

    url = f"{endpoint}{GRANDFATHER_PATH}"
    body = build_request_body(claim)
    name = claim["name"]

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    backoff = INITIAL_BACKOFF_S
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)

            if resp.status_code == 201:
                return SeedResult(name=name, status="created", http_status=201, message="Grandfathered claim created")

            if resp.status_code == 200:
                return SeedResult(name=name, status="exists", http_status=200, message="Already registered (idempotent)")

            if resp.status_code == 409:
                return SeedResult(
                    name=name,
                    status="conflict",
                    http_status=409,
                    message=resp.text[:200],
                )

            if resp.status_code in (400, 401, 403):
                # Client errors — do not retry
                return SeedResult(
                    name=name,
                    status="error",
                    http_status=resp.status_code,
                    message=resp.text[:200],
                )

            # 5xx or unexpected — retry
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"

        except requests.exceptions.ConnectionError as exc:
            last_error = f"Connection error: {exc}"
        except requests.exceptions.Timeout:
            last_error = "Request timed out"
        except requests.exceptions.RequestException as exc:
            last_error = f"Request error: {exc}"

        if attempt < max_retries:
            logger.warning("  Attempt %d/%d failed for '%s': %s — retrying in %.1fs", attempt, max_retries, name, last_error, backoff)
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER

    return SeedResult(name=name, status="error", message=f"Failed after {max_retries} attempts: {last_error}")


# ── Token acquisition ──────────────────────────────────────────────────────

def get_token_via_az_cli(scope: str | None = None, client_id: str | None = None) -> str:
    """Acquire a bearer token using the Azure CLI."""
    resource = scope or (f"api://{client_id}" if client_id else None)
    if not resource:
        raise SystemExit("ERROR: --az-login requires --scope or AZURE_CLIENT_ID to be set")

    cmd = ["az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        token = result.stdout.strip()
        if not token:
            raise SystemExit("ERROR: az CLI returned an empty token")
        return token
    except FileNotFoundError:
        raise SystemExit("ERROR: 'az' CLI not found — install Azure CLI or provide --token")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ERROR: az CLI failed: {exc.stderr.strip()}")


# ── Reporting ──────────────────────────────────────────────────────────────

def print_report(report: SeedReport) -> None:
    """Print a summary of the seeding run."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("SEED RESULTS")
    logger.info("=" * 60)
    logger.info("  Total:     %d", report.total)
    logger.info("  Created:   %d", report.created)
    logger.info("  Exists:    %d (idempotent — already registered)", report.exists)
    logger.info("  Conflict:  %d (name exists with different resource type)", report.conflict)
    logger.info("  Error:     %d", report.error)
    logger.info("")

    if report.conflict > 0 or report.error > 0:
        logger.info("FAILURES:")
        for r in report.results:
            if r.status in ("conflict", "error"):
                logger.info("  ✗ %-40s [%s] %s", r.name, r.status, r.message)
        logger.info("")

    if report.created > 0:
        logger.info("CREATED:")
        for r in report.results:
            if r.status == "created":
                logger.info("  ✓ %s", r.name)
        logger.info("")

    if report.exists > 0:
        logger.info("ALREADY REGISTERED:")
        for r in report.results:
            if r.status == "exists":
                logger.info("  ○ %s", r.name)
        logger.info("")


def write_results_json(report: SeedReport, path: Path) -> None:
    """Write machine-readable results to a JSON file."""
    output = {
        "summary": {
            "total": report.total,
            "created": report.created,
            "exists": report.exists,
            "conflict": report.conflict,
            "error": report.error,
        },
        "results": [
            {
                "name": r.name,
                "status": r.status,
                "http_status": r.http_status,
                "message": r.message,
            }
            for r in report.results
        ],
    }
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    logger.info("Results written to %s", path)


# ── CLI ────────────────────────────────────────────────────────────────────

def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed existing Azure resource names into the naming registry via the grandfather API.",
        epilog="Task 461800 — Build seed and import workflow for existing Azure resource names",
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        help="Path to the JSON seed manifest file.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("NAMING_SERVICE_ENDPOINT", LOCAL_ENDPOINT),
        help="Naming service base URL (default: %(default)s or $NAMING_SERVICE_ENDPOINT)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("NAMING_SERVICE_TOKEN"),
        help="Bearer token for authentication (default: $NAMING_SERVICE_TOKEN). Not needed for local dev.",
    )
    parser.add_argument(
        "--az-login",
        action="store_true",
        help="Acquire a bearer token via 'az account get-access-token' instead of --token.",
    )
    parser.add_argument(
        "--scope",
        default=os.environ.get("NAMING_SERVICE_SCOPE"),
        help="OAuth scope for --az-login token acquisition (default: $NAMING_SERVICE_SCOPE).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the manifest and print what would be seeded without calling the API.",
    )
    parser.add_argument(
        "--results",
        type=Path,
        help="Write machine-readable results JSON to this file path.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=MAX_RETRIES,
        help="Max retry attempts per claim (default: %(default)s).",
    )
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Print a sample manifest to stdout and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = get_parser()
    args = parser.parse_args(argv)

    # ── Generate sample ────────────────────────────────────────────────
    if args.generate_sample:
        print(json.dumps(SAMPLE_MANIFEST, indent=2))
        return 0

    # ── Load manifest ──────────────────────────────────────────────────
    if not args.manifest:
        parser.error("manifest file is required (or use --generate-sample)")

    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        logger.error("Manifest file not found: %s", manifest_path)
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in manifest: %s", exc)
        return 1

    # ── Validate manifest ──────────────────────────────────────────────
    errors = validate_manifest(manifest)
    if errors:
        logger.error("Manifest validation failed:")
        for err in errors:
            logger.error("  - %s", err)
        return 1

    claims: list[dict[str, Any]] = manifest["claims"]
    desc = manifest.get("description", "(no description)")
    logger.info("Manifest: %s", manifest_path.name)
    logger.info("Description: %s", desc)
    logger.info("Claims to seed: %d", len(claims))
    logger.info("Endpoint: %s", args.endpoint)

    # ── Dry run ────────────────────────────────────────────────────────
    if args.dry_run:
        logger.info("")
        logger.info("DRY RUN — no API calls will be made")
        logger.info("")
        for i, claim in enumerate(claims):
            logger.info(
                "  [%d] %-40s  type=%-20s  region=%-5s  env=%-4s",
                i + 1,
                claim["name"],
                claim["resource_type"],
                claim["region"],
                claim["environment"],
            )
        logger.info("")
        logger.info("Manifest is valid. %d claims ready to seed.", len(claims))
        return 0

    # ── Token ──────────────────────────────────────────────────────────
    token = args.token
    if args.az_login and not token:
        client_id = os.environ.get("AZURE_CLIENT_ID")
        token = get_token_via_az_cli(scope=args.scope, client_id=client_id)
        logger.info("Token acquired via Azure CLI")

    if not token and args.endpoint != LOCAL_ENDPOINT:
        logger.warning("No bearer token provided for non-local endpoint — requests may fail with 401")

    # ── Seed ───────────────────────────────────────────────────────────
    report = SeedReport()
    logger.info("")
    for i, claim in enumerate(claims):
        name = claim["name"]
        logger.info("[%d/%d] Seeding '%s' (%s)...", i + 1, len(claims), name, claim["resource_type"])
        result = post_grandfather_claim(args.endpoint, claim, token, max_retries=args.retries)
        report.add(result)

        status_icon = {"created": "✓", "exists": "○", "conflict": "✗", "error": "✗"}.get(result.status, "?")
        logger.info("  %s %s — %s", status_icon, result.status, result.message)

    # ── Report ─────────────────────────────────────────────────────────
    print_report(report)

    if args.results:
        write_results_json(report, args.results)

    # Exit code: 0 if all succeeded or already exist, 1 if any failures
    if report.error > 0 or report.conflict > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
