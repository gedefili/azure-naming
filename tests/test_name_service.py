import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import name_service
from utils.user_settings import InMemorySettingsRepository, UserSettingsService


def test_generate_and_claim_name_success(monkeypatch):
    payload = {
        "resourceType": "storage_account",
        "region": "wus2",
        "environment": "dev",
        "project": "Finance",
        "purpose": "CostReports",
        "system": "ERP",
        "index": "01",
    }

    captured = {}

    monkeypatch.setattr(name_service, "get_slug", lambda resource_type: "st")
    monkeypatch.setattr(name_service, "load_naming_rule", lambda _: {"segments": []})

    def fake_build_name(region, environment, slug, rule, optional_inputs):
        assert region == "wus2"
        assert environment == "dev"
        assert slug == "st"
        assert optional_inputs["domain"] == "finance"
        assert optional_inputs["subdomain"] == "costreports"
        assert optional_inputs["system_short"] == "erp"
        assert optional_inputs["index"] == "01"
        return "sanmar-st-finance-costreports-dev-wus2-01"

    monkeypatch.setattr(name_service, "build_name", fake_build_name)
    monkeypatch.setattr(name_service, "validate_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "check_name_exists", lambda *args, **kwargs: False)

    def fake_claim_name(*args, **kwargs):
        captured["claim_args"] = kwargs

    monkeypatch.setattr(name_service, "claim_name", fake_claim_name)

    def fake_write_audit_log(name, user, action, note, metadata):
        captured["audit"] = {
            "name": name,
            "user": user,
            "action": action,
            "note": note,
            "metadata": metadata,
        }

    monkeypatch.setattr(name_service, "write_audit_log", fake_write_audit_log)

    result = name_service.generate_and_claim_name(payload, requested_by="user@example.com")

    assert result.name == "sanmar-st-finance-costreports-dev-wus2-01"
    assert result.project == "finance"
    assert result.purpose == "costreports"
    assert result.system == "erp"
    assert result.index == "01"

    assert captured["claim_args"]["metadata"]["Project"] == "finance"
    assert captured["audit"]["metadata"]["Region"] == "wus2"
    assert captured["audit"]["metadata"]["Project"] == "finance"


def test_generate_and_claim_name_conflict(monkeypatch):
    payload = {
        "resource_type": "storage_account",
        "region": "wus2",
        "environment": "dev",
    }

    monkeypatch.setattr(name_service, "load_naming_rule", lambda _: {"segments": []})
    monkeypatch.setattr(name_service, "get_slug", lambda _: "st")
    monkeypatch.setattr(name_service, "build_name", lambda **kwargs: "sanmar")
    monkeypatch.setattr(name_service, "validate_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "check_name_exists", lambda *args, **kwargs: True)

    with pytest.raises(name_service.NameConflictError):
        name_service.generate_and_claim_name(payload, requested_by="user@example.com")


@pytest.mark.parametrize(
    "payload,missing",
    [
        ({"region": "wus2", "environment": "dev"}, "resource_type"),
        ({"resource_type": "vm", "environment": "dev"}, "region"),
        ({"resource_type": "vm", "region": "wus2"}, "environment"),
    ],
)
def test_generate_and_claim_name_missing_fields(monkeypatch, payload, missing):
    with pytest.raises(name_service.InvalidRequestError) as exc:
        name_service.generate_and_claim_name(payload, requested_by="user@example.com")
    assert missing in str(exc.value)


def test_generate_and_claim_name_uses_user_defaults(monkeypatch):
    service = UserSettingsService(repository=InMemorySettingsRepository())
    service.set_permanent_defaults(
        "user@example.com",
        {"environment": "dev", "region": "wus2", "resource_type": "storage_account"},
    )

    monkeypatch.setattr(name_service, "settings_service", service)

    payload = {"project": "Finance"}

    monkeypatch.setattr(name_service, "load_naming_rule", lambda _: {"segments": []})
    monkeypatch.setattr(name_service, "get_slug", lambda _: "st")
    monkeypatch.setattr(name_service, "build_name", lambda **kwargs: "sanmar")
    monkeypatch.setattr(name_service, "validate_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "check_name_exists", lambda *args, **kwargs: False)
    monkeypatch.setattr(name_service, "claim_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "write_audit_log", lambda *args, **kwargs: None)

    result = name_service.generate_and_claim_name(payload, requested_by="user@example.com")

    assert result.environment == "dev"
    assert result.region == "wus2"
    assert result.resource_type == "storage_account"
