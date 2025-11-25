"""Unit tests for tools.lib library modules."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from tools.lib import (
    AZURITE_BLOB_PORT,
    AZURITE_QUEUE_PORT,
    AZURITE_TABLE_PORT,
    decode_jwt_claims,
    dev_blob_endpoint,
    dev_queue_endpoint,
    dev_storage_connection_string,
    dev_table_endpoint,
    ensure_directory,
    extract_token_from_cli_output,
    format_expiry_timestamp,
    is_port_open,
    kill_process_by_port,
    run_az_command,
    run_command,
    setup_logging,
    wait_for_port,
    ProcessManager,
)


class TestStorageConfig:
    """Tests for storage_config module."""

    def test_azurite_ports_are_integers(self) -> None:
        """Verify port constants are valid integers."""
        assert isinstance(AZURITE_BLOB_PORT, int)
        assert isinstance(AZURITE_QUEUE_PORT, int)
        assert isinstance(AZURITE_TABLE_PORT, int)
        assert AZURITE_BLOB_PORT == 10000
        assert AZURITE_QUEUE_PORT == 10001
        assert AZURITE_TABLE_PORT == 10002

    def test_dev_storage_connection_string(self) -> None:
        """Verify connection string format."""
        conn_str = dev_storage_connection_string()
        assert "DefaultEndpointsProtocol=http" in conn_str
        assert "127.0.0.1:10000" in conn_str  # Blob
        assert "127.0.0.1:10001" in conn_str  # Queue
        assert "127.0.0.1:10002" in conn_str  # Table

    def test_dev_endpoints(self) -> None:
        """Verify endpoint URLs."""
        assert "10000" in dev_blob_endpoint()
        assert "10001" in dev_queue_endpoint()
        assert "10002" in dev_table_endpoint()


class TestTokenUtils:
    """Tests for token_utils module."""

    def test_format_expiry_timestamp_with_none(self) -> None:
        """Test formatting None timestamp."""
        assert format_expiry_timestamp(None) == "unknown"

    def test_format_expiry_timestamp_with_valid_iso(self) -> None:
        """Test formatting valid ISO timestamp."""
        timestamp = "2025-10-29T14:30:00"
        result = format_expiry_timestamp(timestamp)
        assert result != "unknown"
        assert "2025" in result

    def test_decode_jwt_claims_invalid_format(self) -> None:
        """Test JWT decode with invalid format."""
        with pytest.raises(ValueError):
            decode_jwt_claims("invalid.token")  # Only 2 parts

    def test_extract_token_from_cli_output_found(self) -> None:
        """Test extracting token from output."""
        output = "=== Bearer Token ===\neyJhbGc...\n=== End Token ==="
        token = extract_token_from_cli_output(output)
        assert token == "eyJhbGc..."

    def test_extract_token_from_cli_output_not_found(self) -> None:
        """Test extracting token when markers missing."""
        output = "Some random output"
        token = extract_token_from_cli_output(output)
        assert token is None


class TestProcessUtils:
    """Tests for process_utils module."""

    def test_is_port_open_closed_port(self) -> None:
        """Test checking closed port."""
        # Use high port unlikely to be open
        assert is_port_open(port=54321) is False

    def test_run_command_success(self) -> None:
        """Test running successful command."""
        result = run_command("echo hello", shell=True)
        assert result.returncode == 0

    def test_run_command_failure_no_check(self) -> None:
        """Test running failed command with check=False."""
        result = run_command("false", shell=True, check=False)
        assert result.returncode != 0

    def test_run_command_with_list(self) -> None:
        """Test running command with list args."""
        result = run_command(["echo", "hello"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "hello" in result.stdout

    @mock.patch("subprocess.run")
    def test_run_az_command_success(self, mock_run: mock.Mock) -> None:
        """Test Azure CLI command execution."""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout=json.dumps({"accessToken": "token123"}),
        )
        result = run_az_command(["account", "show"])
        assert result["accessToken"] == "token123"

    def test_run_az_command_not_installed(self) -> None:
        """Test Azure CLI command error handling."""
        with pytest.raises(RuntimeError):
            run_az_command(["nonexistent-command-xyz"])

    def test_wait_for_port_timeout(self) -> None:
        """Test wait_for_port timeout."""
        with pytest.raises(TimeoutError):
            wait_for_port("127.0.0.1", 54321, timeout=0.5)

    @mock.patch("socket.create_connection")
    def test_wait_for_port_success(self, mock_socket: mock.Mock) -> None:
        """Test wait_for_port success."""
        # Simulate socket connection success
        mock_socket.return_value.__enter__ = mock.Mock()
        mock_socket.return_value.__exit__ = mock.Mock(return_value=False)
        # Should not raise
        wait_for_port("127.0.0.1", 7071, timeout=1)

    def test_process_manager_add_and_terminate(self) -> None:
        """Test ProcessManager add and terminate."""
        pm = ProcessManager()
        # Create a simple process
        proc = subprocess.Popen(["sleep", "10"])
        pm.add(proc)
        assert len(pm._children) == 1
        # Terminate
        pm.terminate_all()
        # Give time for termination
        import time
        time.sleep(0.5)
        assert proc.poll() is not None  # Process should be done


class TestBootstrapUtils:
    """Tests for bootstrap_utils module."""

    def test_setup_logging(self) -> None:
        """Test logger setup."""
        logger = setup_logging(level=logging.INFO)
        assert logger is not None
        assert logger.level == logging.INFO

    def test_ensure_directory(self, tmp_path: Path) -> None:
        """Test directory creation."""
        test_dir = tmp_path / "test" / "nested" / "dir"
        ensure_directory(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_existing(self, tmp_path: Path) -> None:
        """Test ensure_directory with existing dir."""
        # Should not raise
        ensure_directory(tmp_path)
        assert tmp_path.exists()
