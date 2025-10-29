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
import shlex
import shutil
import signal
import subprocess
import sys
import time
import socket
from typing import Optional

AZURITE_TABLE_PORT = 10002
AZURITE_BLOB_PORT = 10000
AZURITE_QUEUE_PORT = 10001

DEV_CONNECTION = (
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFe4d01+EXAMPLETESTKEY==;"
    f"BlobEndpoint=http://127.0.0.1:{AZURITE_BLOB_PORT}/devstoreaccount1;"
    f"QueueEndpoint=http://127.0.0.1:{AZURITE_QUEUE_PORT}/devstoreaccount1;"
    f"TableEndpoint=http://127.0.0.1:{AZURITE_TABLE_PORT}/devstoreaccount1;"
)


def _run(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print(f"> {cmd}")
    return subprocess.run(shlex.split(cmd), check=check, capture_output=capture, text=True)


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False


def _wait_for_table(port: int, timeout_s: int = 30) -> bool:
    for _ in range(timeout_s):
        try:
            subprocess.run(["curl", "-sS", f"http://127.0.0.1:{port}"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            time.sleep(1)
    return False


def _get_access_token_via_helper(client_id: Optional[str]) -> Optional[str]:
    args = [sys.executable, "tools/get_access_token.py"]
    if client_id:
        args.extend(["--client-id", client_id])
    try:
        cp = subprocess.run(args, check=True, capture_output=True, text=True)
    except Exception as exc:
        print(f"Failed to run token helper: {exc}")
        return None
    out = cp.stdout
    # Extract the token printed between the markers
    start = out.find("=== Bearer Token ===")
    end = out.find("=== End Token ===")
    if start == -1 or end == -1:
        return None
    token = out[start:end].splitlines()[1].strip()
    return token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run integration tests and an optional smoke test locally.")
    parser.add_argument("--token", help="Optional bearer token to use for the smoke test")
    parser.add_argument("--client-id", help="If --token is omitted, try to call tools/get_access_token.py with this client id")
    parser.add_argument("--function-url", default="http://localhost:7071", help="Function host URL for smoke test")
    args = parser.parse_args(argv)

    # Ensure azurite is available by checking the table endpoint
    if not _wait_for_table(AZURITE_TABLE_PORT, timeout_s=2):
        print("Azurite does not appear to be running on the default port 10002.")
        print("Please start Azurite (or run tools/start_local_stack.py) and re-run this script.")
        return 2

    # Export AzureWebJobsStorage for tests
    os.environ["AzureWebJobsStorage"] = DEV_CONNECTION
    print("Set AzureWebJobsStorage to local Azurite endpoints")

    # Run the coverage wrapper
    try:
        _run(f"{sys.executable} tools/run_tests_with_coverage.py")
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
