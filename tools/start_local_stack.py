"""Bootstrap local Azure Naming stack for debugging.

This script ensures Azurite is running, starts the Azure Functions host with
Python remote debugging enabled, waits until the HTTP endpoints are healthy,
and finally opens the Swagger UI in the default browser.

Designed to be invoked from VS Code tasks or directly from the command line.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# Ports used by the local stack
AZURITE_PORTS = (10000, 10001, 10002)
FUNCTIONS_PORT = 7071
DEBUG_PORT = 5678
DEBUG_HOST = "127.0.0.1"

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
    logger.info(f"Waiting for {host}:{port} (timeout: {timeout}s)...")
    deadline = time.time() + timeout
    attempts = 0
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                logger.info(f"✓ {host}:{port} is now reachable (after {attempts} attempts)")
                return
        except OSError as e:
            attempts += 1
            if attempts % 10 == 0:
                logger.debug(f"  Still waiting for {host}:{port}... ({attempts} attempts)")
            time.sleep(0.2)
    logger.error(f"✗ Timeout waiting for {host}:{port} after {attempts} attempts")
    raise TimeoutError(f"Timeout waiting for {host}:{port}")


def ensure_port_free(host: str, port: int) -> None:
    logger.info(f"Checking if {host}:{port} is available...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            logger.info(f"✓ {host}:{port} is available")
        except OSError as exc:  # pragma: no cover - network state dependent
            logger.error(f"✗ Port {host}:{port} is already in use")
            raise RuntimeError(f"Port {host}:{port} is already in use; stop the owning process or choose another port.") from exc


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def start_azurite(root: Path, manager: ProcessManager, *, use_docker: bool | None = None) -> None:
    """Launch Azurite via CLI or Docker depending on availability."""

    if use_docker is None:
        azurite_cli_available = shutil.which("azurite") is not None
        logger.info(f"Azurite CLI available: {azurite_cli_available}")
        use_docker = not azurite_cli_available

    log_dir = root / ".azurite"
    ensure_directory(log_dir)
    logger.info(f"Azurite log directory: {log_dir}")

    if not use_docker:
        logger.info("Starting Azurite via CLI...")
        cmd = [
            "azurite",
            "--silent",
            "--location",
            str(log_dir),
            "--debug",
            str(log_dir / "debug.log"),
        ]
    else:
        logger.info("Starting Azurite via Docker...")
        if shutil.which("docker") is None:
            logger.error("Docker not found on PATH")
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

    logger.debug(f"Command: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=root)
    manager.add(proc)
    logger.info(f"Azurite process started (PID: {proc.pid})")

    # Give Azurite a moment before probing ports
    logger.info("Waiting for Azurite ports to become available...")
    for port in AZURITE_PORTS:
        wait_for_port("127.0.0.1", port, timeout=20)
    logger.info("✓ All Azurite ports are reachable")


def start_functions(
    root: Path,
    manager: ProcessManager,
    *,
    wait_for_client: bool,
) -> None:
    logger.info("Starting Azure Functions host...")
    env = os.environ.copy()

    venv_bin = root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    if venv_bin.exists():
        logger.info(f"Virtual environment found: {venv_bin}")
        path_sep = ";" if os.name == "nt" else ":"
        env["PATH"] = str(venv_bin) + path_sep + env.get("PATH", "")
        env.setdefault("VIRTUAL_ENV", str(root / ".venv"))
    else:
        logger.warning(f"Virtual environment not found at {venv_bin}")

    logger.info(f"Checking if debug port {DEBUG_PORT} is available...")
    ensure_port_free(DEBUG_HOST, DEBUG_PORT)

    debug_args = f"-m debugpy --listen {DEBUG_HOST}:{DEBUG_PORT}"
    if wait_for_client:
        debug_args += " --wait-for-client"
        logger.info("Debug mode: waiting for client attach")
    else:
        logger.info("Debug mode: not waiting for client")

    env.setdefault("FUNCTIONS_WORKER_PROCESS_COUNT", "1")
    env.setdefault("languageWorkers__python__arguments", debug_args)
    logger.debug(f"Python worker args: {debug_args}")

    func_exe = shutil.which("func")
    if not func_exe:
        logger.error("Azure Functions Core Tools (func) not found on PATH")
        raise RuntimeError(
            "Azure Functions Core Tools (func) not found on PATH. Install them or make sure they are accessible."
        )

    logger.info(f"Functions CLI: {func_exe}")
    func_cmd: Sequence[str] = (func_exe, "start", "--verbose")
    logger.debug(f"Command: {' '.join(func_cmd)}")

    logger.info("Launching Functions host process...")
    proc = subprocess.Popen(func_cmd, cwd=root, env=env)
    manager.add(proc)
    logger.info(f"Functions host process started (PID: {proc.pid})")

    logger.info(f"Waiting for Functions host to be ready on port {FUNCTIONS_PORT}...")
    wait_for_port("127.0.0.1", FUNCTIONS_PORT, timeout=60)

    print(PRINT_FUNC_READY, flush=True)

    print(f"Swagger UI available at http://localhost:{FUNCTIONS_PORT}/api/docs", flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    logger.info("=== Azure Naming Local Stack Bootstrap ===")
    parser = argparse.ArgumentParser(description="Start local Azure Naming stack")
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
    parser.add_argument(
        "--wait-for-client",
        action="store_true",
        help="Pause the Python worker until a debugger attaches.",
    )
    args = parser.parse_args(argv)
    logger.info(f"Arguments: use_docker={args.use_docker}, no_docker={args.no_docker}, wait_for_client={args.wait_for_client}")

    root = Path(__file__).resolve().parents[1]
    logger.info(f"Working directory: {root}")
    manager = ProcessManager()

    def _shutdown(signum: int, frame: object | None) -> None:  # pragma: no cover - signal handler
        logger.info(f"Received signal {signum}, shutting down...")
        manager.terminate_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    print(PRINT_STACK_START, flush=True)

    try:
        start_azurite(root, manager, use_docker=args.use_docker if not args.no_docker else False)
        start_functions(
            root,
            manager,
            wait_for_client=args.wait_for_client,
        )
        logger.info(
            f"✓ Local stack is ready!\n"
            f"  Functions: http://localhost:{FUNCTIONS_PORT}\n"
            f"  Swagger UI: http://localhost:{FUNCTIONS_PORT}/api/docs\n"
            f"  Debugger: {DEBUG_HOST}:{DEBUG_PORT}"
        )
        print(
            f"📡 Functions host running on http://localhost:{FUNCTIONS_PORT}.",
            f" Attach your debugger to port {DEBUG_PORT}.",
            sep="\n",
            flush=True,
        )
        logger.info("Waiting for Functions host process...")
        manager._children[-1].wait()
        logger.info("Functions host process exited")
    except KeyboardInterrupt:  # pragma: no cover - handled by signal
        logger.info("Interrupted by user")
        pass
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1
    finally:
        logger.info("Cleaning up...")
        manager.terminate_all()

    logger.info("Stack shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
