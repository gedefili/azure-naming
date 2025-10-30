import pathlib
import random
import string
import sys

import json

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import name_service, naming_rules
from core.user_settings import InMemorySettingsRepository, UserSettingsService
from providers.json_rules import JsonRuleProvider


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
    assert result.metadata["Project"] == "finance"
    assert result.metadata["Purpose"] == "costreports"
    assert result.system == "erp"
    assert result.metadata["Index"] == "01"

    assert captured["claim_args"]["metadata"]["Project"] == "finance"
    assert captured["audit"]["metadata"]["Region"] == "wus2"
    assert captured["audit"]["metadata"]["Project"] == "finance"


def test_generate_and_claim_name_conflict(monkeypatch):
    payload = {
        "resource_type": "storage_account",
        "region": "wus2",
        "environment": "dev",
    }

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


def test_generate_and_claim_name_for_sample_combinations(monkeypatch):
    resource_samples = [
        {
            "resource_type": "storage_account",
            "slug": "st",
        },
        {
            "resource_type": "app_service",
            "slug": "app",
            "project": "commerce",
            "purpose": "checkout",
            "index": "01",
        },
        {
            "resource_type": "key_vault",
            "slug": "kv",
            "project": "security",
            "purpose": "secrets",
            "index": "02",
        },
        {
            "resource_type": "virtual_machine",
            "slug": "vm",
            "project": "analytics",
            "purpose": "batch",
            "index": "03",
        },
        {
            "resource_type": "sql_server",
            "slug": "sql",
            "project": "finance",
            "purpose": "reporting",
            "index": "04",
        },
    ]

    slug_lookup = {sample["resource_type"].lower(): sample["slug"] for sample in resource_samples}
    environments = ["Dev", "Qa", "PROD"]
    regions = ["wus2", "EUS2", "UKS"]

    claimed_records = []
    audit_records = []

    monkeypatch.setattr(
        name_service,
        "get_slug",
        lambda resource_type: slug_lookup[resource_type.lower()],
    )
    monkeypatch.setattr(name_service, "check_name_exists", lambda *args, **kwargs: False)

    def fake_claim_name(*, region, environment, name, resource_type, claimed_by, metadata):
        claimed_records.append(
            {
                "region": region,
                "environment": environment,
                "name": name,
                "resource_type": resource_type,
                "claimed_by": claimed_by,
                "metadata": metadata,
            }
        )

    monkeypatch.setattr(name_service, "claim_name", fake_claim_name)

    def fake_write_audit_log(name, user, action, note, metadata):
        audit_records.append(
            {
                "name": name,
                "user": user,
                "action": action,
                "note": note,
                "metadata": metadata,
            }
        )

    monkeypatch.setattr(name_service, "write_audit_log", fake_write_audit_log)

    random_gen = random.Random(2024)
    generated_names = []

    for sample in resource_samples:
        resource_type = sample["resource_type"]
        slug = sample["slug"]
        project = sample.get("project")
        purpose = sample.get("purpose")
        index_value = sample.get("index")

        for environment in environments:
            expected_environment = environment.lower()
            for region in regions:
                expected_region = region.lower()
                system_length = 3 if resource_type == "storage_account" else 6
                system_name = "".join(
                    random_gen.choices(string.ascii_lowercase, k=system_length)
                )

                payload = {
                    "resource_type": resource_type,
                    "environment": environment,
                    "region": region,
                    "system": system_name,
                }
                if project:
                    payload["project"] = project
                if purpose:
                    payload["purpose"] = purpose
                if index_value:
                    payload["index"] = index_value

                result = name_service.generate_and_claim_name(
                    payload, requested_by="tester@example.com"
                )

                expected_parts = [slug, system_name]
                if project:
                    expected_parts.append(project)
                if purpose:
                    expected_parts.append(purpose)
                expected_parts.extend([expected_environment, expected_region])
                if index_value:
                    expected_parts.append(index_value)

                expected_name = "-".join(expected_parts)
                if resource_type == "storage_account":
                    expected_name = f"sanmar-{expected_name}"

                assert result.name == expected_name
                assert result.slug == slug
                assert result.environment == expected_environment
                assert result.region == expected_region
                assert result.resource_type == resource_type
                if project:
                    assert result.project == project
                else:
                    assert result.project is None
                if purpose:
                    assert result.purpose == purpose
                else:
                    assert result.purpose is None
                if index_value:
                    assert result.index == index_value
                else:
                    assert result.index is None
                assert result.system == system_name

                generated_names.append(result.name)

                claim = claimed_records[-1]
                assert claim["region"] == expected_region
                assert claim["environment"] == expected_environment
                assert claim["name"] == expected_name
                assert claim["resource_type"] == resource_type
                assert claim["claimed_by"] == "tester@example.com"
                metadata = claim["metadata"]
                assert metadata["Slug"] == slug
                assert metadata["System"] == system_name
                if project:
                    assert metadata["Project"] == project
                else:
                    assert "Project" not in metadata
                if purpose:
                    assert metadata["Purpose"] == purpose
                else:
                    assert "Purpose" not in metadata
                if index_value:
                    assert metadata["Index"] == index_value
                else:
                    assert "Index" not in metadata

                audit = audit_records[-1]
                assert audit["name"] == expected_name
                assert audit["user"] == "tester@example.com"
                assert audit["action"] == "claimed"
                assert audit["metadata"]["Slug"] == slug
                assert audit["metadata"]["Region"] == expected_region
                assert audit["metadata"]["Environment"] == expected_environment
                assert audit["metadata"]["System"] == system_name
                if project:
                    assert audit["metadata"]["Project"] == project
                if purpose:
                    assert audit["metadata"]["Purpose"] == purpose
                if index_value:
                    assert audit["metadata"]["Index"] == index_value

    expected_total = len(resource_samples) * len(environments) * len(regions)
    assert len(generated_names) == expected_total
    assert len(claimed_records) == expected_total
    assert len(audit_records) == expected_total
    # Ensure names are unique across combinations
    assert len(set(generated_names)) == expected_total


def test_to_dict_includes_display(monkeypatch):
    payload = {
        "resource_type": "storage_account",
        "region": "wus2",
        "environment": "dev",
    }

    monkeypatch.setattr(name_service, "get_slug", lambda _: "st")
    monkeypatch.setattr(name_service, "build_name", lambda **kwargs: "sanmar-st-dev-wus2")
    monkeypatch.setattr(name_service, "validate_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "check_name_exists", lambda *args, **kwargs: False)
    monkeypatch.setattr(name_service, "claim_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "write_audit_log", lambda *args, **kwargs: None)

    result = name_service.generate_and_claim_name(payload, requested_by="user@example.com")

    body = result.to_dict()
    assert "display" in body
    assert any(entry["key"] == "name" for entry in body["display"])


def _build_us_strict_provider(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    base_path = ROOT / "rules" / "base.json"
    rules_dir.joinpath("base.json").write_text(base_path.read_text(encoding="utf-8"), encoding="utf-8")

    overlay = {
        "metadata": {"name": "us_strict", "priority": 100},
        "resources": {
            "storage_account": {
                "segments": [
                    "slug",
                    "system_short",
                    "subdomain",
                    "environment",
                    "region",
                    "index",
                ],
                "require_sanmar_prefix": True,
                "name_template": "{region}-{environment}-{slug}-{system_short}{index_segment}",
                "summary_template": "Storage account '{name}' for system '{system_upper}' in {environment_upper}-{region_upper}",
                "validators": {
                    "allowed_values": {
                        "region": ["wus", "wus2", "eus", "eus1"],
                        "environment": ["prd", "stg", "tst", "uat", "alt"],
                    },
                    "require_any": {
                        "system": ["system", "system_short"],
                        "subsystem": ["purpose", "subdomain"],
                    },
                }
            }
        },
    }
    rules_dir.joinpath("us_strict.json").write_text(json.dumps(overlay), encoding="utf-8")
    return JsonRuleProvider(rules_path=rules_dir)


def test_us_provider_enforces_region(monkeypatch, tmp_path):
    provider = _build_us_strict_provider(tmp_path)
    original_provider = naming_rules.get_rule_provider()
    naming_rules.set_rule_provider(provider)

    payload = {
        "resource_type": "storage_account",
        "region": "weu",
        "environment": "prd",
        "system": "erp",
        "purpose": "billing",
    }

    monkeypatch.setattr(name_service, "get_slug", lambda _: "st")
    monkeypatch.setattr(name_service, "build_name", lambda **kwargs: "sanmar")
    monkeypatch.setattr(name_service, "validate_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "check_name_exists", lambda *args, **kwargs: False)
    monkeypatch.setattr(name_service, "claim_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "write_audit_log", lambda *args, **kwargs: None)

    try:
        with pytest.raises(name_service.InvalidRequestError) as exc:
            name_service.generate_and_claim_name(payload, requested_by="user@example.com")
        assert "region" in str(exc.value)
    finally:
        naming_rules.set_rule_provider(original_provider)


def test_us_provider_accepts_valid_payload(monkeypatch, tmp_path):
    provider = _build_us_strict_provider(tmp_path)
    original_provider = naming_rules.get_rule_provider()
    naming_rules.set_rule_provider(provider)

    payload = {
        "resource_type": "storage_account",
        "region": "wus",
        "environment": "prd",
        "system": "erp",
        "purpose": "billing",
        "index": "01",
    }

    captured = {}

    monkeypatch.setattr(name_service, "get_slug", lambda _: "st")
    monkeypatch.setattr(name_service, "build_name", lambda **kwargs: "sanmar-st-erp-billing-prd-wus-01")
    monkeypatch.setattr(name_service, "validate_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(name_service, "check_name_exists", lambda *args, **kwargs: False)
    monkeypatch.setattr(name_service, "claim_name", lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(name_service, "write_audit_log", lambda *args, **kwargs: None)

    try:
        result = name_service.generate_and_claim_name(payload, requested_by="user@example.com")
        assert result.name == "sanmar-st-erp-billing-prd-wus-01"
        assert result.rule is provider.get_rule("storage_account")
        result_payload = result.to_dict()
        assert any(entry["key"] == "system" for entry in result_payload["display"])
        assert result_payload["summary"] == (
            "Storage account 'sanmar-st-erp-billing-prd-wus-01' for system 'ERP' in PRD-WUS"
        )
    finally:
        naming_rules.set_rule_provider(original_provider)
