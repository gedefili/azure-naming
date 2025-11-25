"""Process and subprocess utilities for tool scripts.

Centralized subprocess execution, port management, and process lifecycle
management. Provides cross-platform port checking and process termination.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)


def run_command(
    cmd: str | list[str],
    check: bool = True,
    capture_output: bool = False,
    shell: bool = False,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a command with optional output capture.

    Args:
        cmd: Command as string or list of args
        check: Raise on non-zero exit code
        capture_output: Capture stdout/stderr
        shell: Run through shell
        text: Return str instead of bytes

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Raises:
        subprocess.CalledProcessError: If check=True and command fails
    """
    if isinstance(cmd, str):
        cmd = cmd.split() if not shell else cmd
    
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            shell=shell,
            text=text,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"Command not found: {cmd[0] if isinstance(cmd, list) else cmd.split()[0]}") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed with exit code {e.returncode}: {e.stderr or e.stdout or str(e)}") from e


def run_az_command(args: list[str]) -> dict[str, Any]:
    """Execute Azure CLI command and return JSON output.

    Args:
        args: Args to pass to 'az' (without 'az' prefix, without '-o json')

    Returns:
        Parsed JSON response from Azure CLI

    Raises:
        RuntimeError: If Azure CLI not installed or command fails
    """
    try:
        completed = subprocess.run(
            ["az", *args, "-o", "json"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Azure CLI (az) is not installed or not on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.strip() or exc.stdout.strip() or str(exc)) from exc

    try:
        import json
        return json.loads(completed.stdout)
    except Exception as exc:
        raise RuntimeError("Failed to parse Azure CLI output as JSON.") from exc


def is_port_open(
    host: str = "127.0.0.1",
    port: int = 7071,
    timeout: float = 0.5,
) -> bool:
    """Check if a port is open (socket connection succeeds).

    Args:
        host: Hostname/IP to connect to
        port: Port number
        timeout: Connection timeout in seconds

    Returns:
        True if port is open, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            return sock.connect_ex((host, port)) == 0
        except Exception:
            return False


def wait_for_port(
    host: str,
    port: int,
    timeout: float = 60.0,
    poll_interval: float = 0.2,
    logger_obj: logging.Logger | None = None,
) -> None:
    """Poll until port opens or timeout.

    Args:
        host: Hostname to connect to
        port: Port number
        timeout: Max wait time in seconds
        poll_interval: Time between checks
        logger_obj: Optional logger for debug messages

    Raises:
        TimeoutError: If port doesn't open within timeout
    """
    log = logger_obj or logger
    log.info(f"Waiting for {host}:{port} (timeout: {timeout}s)...")
    
    deadline = time.time() + timeout
    attempts = 0
    
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                log.info(f"✓ {host}:{port} is now reachable (after {attempts} attempts)")
                return
        except OSError:
            attempts += 1
            if attempts % 10 == 0:
                log.debug(f"  Still waiting for {host}:{port}... ({attempts} attempts)")
            time.sleep(poll_interval)
    
    log.error(f"✗ Timeout waiting for {host}:{port} after {attempts} attempts")
    raise TimeoutError(f"Timeout waiting for {host}:{port}")


def kill_process_by_port(port: int, logger_obj: logging.Logger | None = None) -> None:
    """Kill process holding the port (cross-platform).

    Supports:
    - Windows: Uses 'netstat -ano | findstr' + 'taskkill /F /PID'
    - Linux/macOS: Uses 'lsof -ti' + 'kill -9'

    Args:
        port: Port number to free
        logger_obj: Optional logger for debug messages

    Logs errors but does not raise on failure (best-effort cleanup).
    """
    log = logger_obj or logger
    try:
        if os.name == "nt":  # Windows
            cmd = f'netstat -ano | findstr ":{port}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        log.debug(f"Killing PID {pid} holding port {port}")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
        else:  # Linux/macOS
            cmd = f"lsof -ti:{port}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    log.debug(f"Killing PID {pid} holding port {port}")
                    subprocess.run(f"kill -9 {pid}", shell=True)
        time.sleep(0.2)
    except Exception as e:
        log.debug(f"Failed to kill port holder: {e}")


class ProcessManager:
    """Track and cleanly terminate child processes."""

    def __init__(self) -> None:
        """Initialize empty process list."""
        self._children: list[subprocess.Popen[bytes]] = []

    def add(self, proc: subprocess.Popen[bytes]) -> None:
        """Add process to tracking list.

        Args:
            proc: Process object from subprocess.Popen()
        """
        self._children.append(proc)

    def terminate_all(self) -> None:
        """Terminate all tracked processes gracefully.

        First sends SIGTERM to all processes in reverse order,
        then waits up to 5 seconds. If any survive, sends SIGKILL.
        """
        for proc in reversed(self._children):
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    continue
        
        for proc in reversed(self._children):
            if proc.poll() is None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
