#!/usr/bin/env python3
"""
Repository: azure-naming
Path: tools/verify_deployment.py
Purpose: Post-deployment verification for the Azure Naming Function App
Author: SanMar Platform Team
Created: 2026-04-14
Last-Modified: 2026-04-14
Version: 1.4.0
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time


DEFAULT_APP_NAME = "wus2-prd-fn-aznaming"
DEFAULT_RESOURCE_GROUP = "wus2-prd-rg-aznaming"
EXPECTED_MIN_FUNCTIONS = 8


def run_az(args: list[str]) -> str:
    result = subprocess.run(
        ["az", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"az {' '.join(args)} failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def check_functions_registered(app_name: str, resource_group: str) -> int:
    print(f"Checking registered functions for {app_name}...")
    output = run_az([
        "functionapp", "function", "list",
        "-n", app_name,
        "-g", resource_group,
        "-o", "json",
    ])
    functions = json.loads(output)
    names = [f.get("name", "unknown") for f in functions]
    print(f"  Registered functions ({len(names)}): {', '.join(sorted(names))}")
    return len(names)


def check_app_settings(app_name: str, resource_group: str) -> dict[str, str]:
    print(f"Checking app settings for {app_name}...")
    output = run_az([
        "functionapp", "config", "appsettings", "list",
        "-n", app_name,
        "-g", resource_group,
        "-o", "json",
    ])
    settings = {s["name"]: s.get("value", "") for s in json.loads(output)}

    issues: list[str] = []

    wrfp = settings.get("WEBSITE_RUN_FROM_PACKAGE", "")
    if wrfp and wrfp != "0":
        issues.append(
            f"  WARNING: WEBSITE_RUN_FROM_PACKAGE is set to '{wrfp}'. "
            "This should be removed or set to '0' for remote-build deployments."
        )
    else:
        print("  OK: WEBSITE_RUN_FROM_PACKAGE is not set (remote build mode)")

    scm = settings.get("SCM_DO_BUILD_DURING_DEPLOYMENT", "")
    if scm.lower() != "true":
        issues.append(
            "  WARNING: SCM_DO_BUILD_DURING_DEPLOYMENT is not 'true'. "
            "Remote builds may not execute pip install."
        )
    else:
        print("  OK: SCM_DO_BUILD_DURING_DEPLOYMENT=true")

    oryx = settings.get("ENABLE_ORYX_BUILD", "")
    if oryx.lower() != "true":
        issues.append(
            "  WARNING: ENABLE_ORYX_BUILD is not 'true'. "
            "Server-side build may not work correctly."
        )
    else:
        print("  OK: ENABLE_ORYX_BUILD=true")

    runtime = settings.get("FUNCTIONS_WORKER_RUNTIME", "")
    print(f"  Runtime: {runtime}")

    for issue in issues:
        print(issue)

    return settings


def smoke_test_endpoint(app_name: str) -> bool:
    url = f"https://{app_name}.azurewebsites.net/api/docs"
    print(f"Smoke testing {url}...")
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url, "--max-time", "15"],
            capture_output=True,
            text=True,
        )
        code = result.stdout.strip()
        print(f"  HTTP {code}")
        if code == "404":
            print("  FAIL: /api/docs returned 404 — functions are not registered")
            return False
        print("  OK: Endpoint is reachable")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Azure Naming Function App deployment")
    parser.add_argument("--app-name", default=DEFAULT_APP_NAME, help="Function App name")
    parser.add_argument("--resource-group", default=DEFAULT_RESOURCE_GROUP, help="Resource group")
    parser.add_argument("--wait", type=int, default=0, help="Seconds to wait before checking")
    args = parser.parse_args()

    if args.wait > 0:
        print(f"Waiting {args.wait}s for deployment to stabilize...")
        time.sleep(args.wait)

    print("=" * 60)
    print("Azure Naming Function App — Deployment Verification")
    print("=" * 60)
    print()

    errors = 0

    # Check app settings
    check_app_settings(args.app_name, args.resource_group)
    print()

    # Check functions
    count = check_functions_registered(args.app_name, args.resource_group)
    if count < EXPECTED_MIN_FUNCTIONS:
        print(f"  FAIL: Expected at least {EXPECTED_MIN_FUNCTIONS} functions, got {count}")
        errors += 1
    else:
        print(f"  OK: {count} functions registered")
    print()

    # Smoke test
    if not smoke_test_endpoint(args.app_name):
        errors += 1
    print()

    print("=" * 60)
    if errors > 0:
        print(f"VERIFICATION FAILED — {errors} issue(s) detected")
        return 1
    print("VERIFICATION PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
