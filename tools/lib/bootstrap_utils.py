"""Bootstrap utilities for tool scripts.

Provides logging setup, process monitoring, and directory utilities
for bootstrap scripts. Designed for local development environment initialization.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from . import process_utils


def setup_logging(
    level: str | int = logging.DEBUG,
    format_str: str = "[%(levelname)s] %(message)s",
    stream=sys.stderr,
) -> logging.Logger:
    """Configure and return root logger.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_str: Log message format
        stream: Output stream (default: stderr)

    Returns:
        Configured root logger instance
    """
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    formatter = logging.Formatter(format_str)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


def watchdog_port_binding(
    proc: subprocess.Popen[bytes],
    port: int,
    timeout: float,
    logger_obj: Optional[logging.Logger] = None,
) -> None:
    """Monitor process; kill if doesn't bind to port within timeout.

    Runs in a background thread. Polls port every 0.5 seconds.
    Logs progress every 20 checks (~10 seconds).

    Args:
        proc: Process object to monitor
        port: Expected port to bind to
        timeout: Max wait time in seconds
        logger_obj: Optional logger

    Raises:
        TimeoutError: If port not bound after timeout (kills process first)
    """
    logger = logger_obj or logging.getLogger(__name__)
    
    deadline = time.time() + timeout
    check_count = 0
    
    while time.time() < deadline:
        if proc.poll() is not None:
            logger.debug(f"Process {proc.pid} exited before binding to port {port}")
            return
        
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                logger.debug(f"Watchdog: process {proc.pid} successfully bound to port {port}")
                return
        except OSError:
            pass
        
        check_count += 1
        if check_count % 20 == 0:  # Log every 20 checks (every 10 seconds)
            elapsed = time.time() - (deadline - timeout)
            logger.debug(
                f"Watchdog: still waiting for port {port}... "
                f"({elapsed:.1f}s elapsed, {timeout - elapsed:.1f}s remaining)"
            )
        
        time.sleep(0.5)
    
    logger.error(
        f"Watchdog timeout: process {proc.pid} did not bind to port {port} within {timeout}s. Killing it."
    )
    try:
        proc.terminate()
        time.sleep(1)
        if proc.poll() is None:
            logger.warning(f"Process {proc.pid} did not respond to SIGTERM, sending SIGKILL...")
            proc.kill()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.error(f"Process {proc.pid} did not exit after SIGKILL")
        proc.kill()
    
    raise TimeoutError(f"Process {proc.pid} failed to bind to port {port} within {timeout}s")


def ensure_directory(path: Path) -> None:
    """Create directory with parents (like mkdir -p).

    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)
