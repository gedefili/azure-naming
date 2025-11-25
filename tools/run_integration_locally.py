"""Run integration tests locally with Azurite and optional authenticated smoke test.

This helper performs the following steps:
- Ensures Azurite is running (tries to start it as a background process if available),
- Sets AzureWebJobsStorage to point at local Azurite table endpoint,
- Runs the project's coverage wrapper `tools/run_tests_with_coverage.py`,
- Optionally runs an authenticated smoke test against the local function host using
  either an explicit token provided by --token or by calling tools/get_access_token.py.

This avoids embedding token-resolution logic in the CI workflow and makes local
integration runs reproducible.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Optional

# Support both running from workspace root and tools directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.lib import (
    AZURITE_BLOB_PORT,
    AZURITE_QUEUE_PORT,
    AZURITE_TABLE_PORT,
    dev_storage_connection_string,
    extract_token_from_cli_output,
    run_command,
    wait_for_port,
)


def _get_access_token_via_helper(client_id: Optional[str]) -> Optional[str]:
    args = [sys.executable, "tools/get_access_token.py"]
    if client_id:
        args.extend(["--client-id", client_id])
    try:
        cp = run_command(args, check=True, capture_output=True, text=True)
    except Exception as exc:
        print(f"Failed to run token helper: {exc}")
        return None
    token = extract_token_from_cli_output(cp.stdout)
    return token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run integration tests and an optional smoke test locally.")
    parser.add_argument("--token", help="Optional bearer token to use for the smoke test")
    parser.add_argument("--client-id", help="If --token is omitted, try to call tools/get_access_token.py with this client id")
    parser.add_argument("--function-url", default="http://localhost:7071", help="Function host URL for smoke test")
    args = parser.parse_args(argv)

    # Ensure azurite is available by checking the table endpoint
    try:
        wait_for_port("127.0.0.1", AZURITE_TABLE_PORT, timeout=2)
    except TimeoutError:
        print("Azurite does not appear to be running on the default port 10002.")
        print("Please start Azurite (or run tools/start_local_stack.py) and re-run this script.")
        return 2

    # Export AzureWebJobsStorage for tests
    os.environ["AzureWebJobsStorage"] = dev_storage_connection_string()
    print("Set AzureWebJobsStorage to local Azurite endpoints")

    # Run the coverage wrapper
    try:
        run_command([sys.executable, "tools/run_tests_with_coverage.py"], check=True)
    except subprocess.CalledProcessError as exc:
        print("Integration tests failed (see output above)")
        return exc.returncode

    # If smoke test token not provided, try helper
    token = args.token
    if not token and args.client_id:
        token = _get_access_token_via_helper(args.client_id)

    if token:
        print(f"Running authenticated smoke test against {args.function_url}")
        try:
            cp = subprocess.run([
                "curl",
                "-sS",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "-H",
                f"Authorization: Bearer {token}",
                f"{args.function_url}/api/slug?resource_type=storage_account",
            ], check=False, capture_output=True, text=True)
            status = cp.stdout.strip()
            print(f"Smoke test HTTP status: {status}")
            if status and int(status) >= 400:
                print("Smoke test failed")
                return 3
        except Exception as exc:
            print(f"Smoke test execution failed: {exc}")
            return 4

    print("Integration run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
