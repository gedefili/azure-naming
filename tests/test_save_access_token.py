from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import save_access_token


def test_fetch_token_via_az_uses_supported_arguments(monkeypatch):
    captured: list[list[str]] = []

    def fake_run_az_command(args: list[str]):
        captured.append(args)
        return {
            "accessToken": "token-value",
            "tenant": "tenant-id",
            "expiresOn": "2026-04-07T23:00:00+00:00",
        }

    monkeypatch.setattr(save_access_token, "run_az_command", fake_run_az_command)

    token, tenant_id, expires_on = save_access_token._fetch_token_via_az(
        tenant_id="tenant-id",
        api_client_id="api-id",
        resource=None,
        scope=None,
    )

    assert token == "token-value"
    assert tenant_id == "tenant-id"
    assert expires_on == "2026-04-07T23:00:00+00:00"
    assert captured == [["account", "get-access-token", "--tenant", "tenant-id", "--resource", "api://api-id"]]


def test_main_preserves_existing_env_ids_when_saving_token(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "FUNCTION_BASE_URL=https://example.internal\n"
        "AZURE_TENANT_ID=existing-tenant\n"
        "AZURE_CLIENT_ID=existing-api\n"
        "TEST_CLIENT_ID=existing-client\n"
        "ACCESS_TOKEN=old-token\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("FUNCTION_BASE_URL", raising=False)
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("TEST_CLIENT_ID", raising=False)
    monkeypatch.delenv("ACCESS_TOKEN", raising=False)

    exit_code = save_access_token.main(["--env-file", str(env_path), "--token", "new-token"])

    assert exit_code == 0
    assert env_path.read_text(encoding="utf-8") == (
        "FUNCTION_BASE_URL=https://example.internal\n"
        "AZURE_TENANT_ID=existing-tenant\n"
        "AZURE_CLIENT_ID=existing-api\n"
        "TEST_CLIENT_ID=existing-client\n"
        "ACCESS_TOKEN=new-token\n"
    )