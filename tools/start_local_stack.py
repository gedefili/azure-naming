"""Bootstrap local Azure Naming stack for debugging.

This script ensures Azurite is running, starts the Azure Functions host with
Python remote debugging enabled, waits until the HTTP endpoints are healthy,
and finally opens the Swagger UI in the default browser.

Designed to be invoked from VS Code tasks or directly from the command line.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Sequence


# Ports used by the local stack
AZURITE_PORTS = (10000, 10001, 10002)
FUNCTIONS_PORT = 7071
DEBUG_PORT = 5678

# Marker strings consumed by VS Code background problem matchers
PRINT_STACK_START = "__DEV_STACK_STARTING__"
PRINT_FUNC_READY = "__FUNC_HOST_READY__"


class ProcessManager:
    """Thin helper to keep track of child processes and terminate them cleanly."""

    def __init__(self) -> None:
        self._children: list[subprocess.Popen[bytes]] = []

    def add(self, proc: subprocess.Popen[bytes]) -> None:
        self._children.append(proc)

    def terminate_all(self) -> None:
        for proc in reversed(self._children):
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:  # pragma: no cover - best effort cleanup
                    continue
        for proc in reversed(self._children):
            if proc.poll() is None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


def wait_for_port(host: str, port: int, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"Timeout waiting for {host}:{port}")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def start_azurite(root: Path, manager: ProcessManager, *, use_docker: bool | None = None) -> None:
    """Launch Azurite via CLI or Docker depending on availability."""

    if use_docker is None:
        use_docker = shutil.which("azurite") is None

    log_dir = root / ".azurite"
    ensure_directory(log_dir)

    if not use_docker:
        cmd = [
            "azurite",
            "--silent",
            "--location",
            str(log_dir),
            "--debug",
            str(log_dir / "debug.log"),
        ]
    else:
        if shutil.which("docker") is None:
            raise RuntimeError(
                "Azurite CLI not found and Docker is unavailable. Install either azurite CLI or Docker."
            )
        cmd = [
            "docker",
            "run",
            "--rm",
            "-p",
            "10000:10000",
            "-p",
            "10001:10001",
            "-p",
            "10002:10002",
            "mcr.microsoft.com/azure-storage/azurite",
        ]

    proc = subprocess.Popen(
        cmd,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    manager.add(proc)

    # Give Azurite a moment before probing ports
    for port in AZURITE_PORTS:
        wait_for_port("127.0.0.1", port, timeout=20)


def start_functions(root: Path, manager: ProcessManager, *, open_swagger: bool) -> None:
    env = os.environ.copy()

    venv_bin = root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    if venv_bin.exists():
        path_sep = ";" if os.name == "nt" else ":"
        env["PATH"] = str(venv_bin) + path_sep + env.get("PATH", "")
        env.setdefault("VIRTUAL_ENV", str(root / ".venv"))

    env.setdefault(
        "languageWorkers__python__arguments",
        "-m debugpy --listen 0.0.0.0:{port} --wait-for-client".format(port=DEBUG_PORT),
    )

    func_cmd: Sequence[str] = ("func", "start", "--verbose")

    proc = subprocess.Popen(
        func_cmd,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    manager.add(proc)

    wait_for_port("127.0.0.1", FUNCTIONS_PORT, timeout=60)

    print(PRINT_FUNC_READY, flush=True)

    if open_swagger:
        # Wait until Swagger responds with HTTP 200 before opening the browser.
        deadline = time.time() + 30
        url = "http://localhost:7071/api/docs"
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", FUNCTIONS_PORT), timeout=2):
                    webbrowser.open(url)
                    break
            except OSError:
                time.sleep(0.5)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start local Azure Naming stack")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not launch the Swagger UI automatically.",
    )
    parser.add_argument(
        "--use-docker",
        action="store_true",
        help="Force using Docker to run Azurite even if the CLI is available.",
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Fail if the Azurite CLI is missing instead of falling back to Docker.",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    manager = ProcessManager()

    def _shutdown(signum: int, frame: object | None) -> None:  # pragma: no cover - signal handler
        manager.terminate_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    print(PRINT_STACK_START, flush=True)

    try:
        start_azurite(root, manager, use_docker=args.use_docker if not args.no_docker else False)
        start_functions(root, manager, open_swagger=not args.no_browser)
        print(
            f"📡 Functions host running on http://localhost:{FUNCTIONS_PORT}.",
            f" Attach your debugger to port {DEBUG_PORT}.",
            sep="\n",
            flush=True,
        )
        manager._children[-1].wait()
    except KeyboardInterrupt:  # pragma: no cover - handled by signal
        pass
    finally:
        manager.terminate_all()

    return 0


if __name__ == "__main__":
    sys.exit(main())
