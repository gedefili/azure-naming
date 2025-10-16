import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.json_rules import JsonRuleProvider


def _write_rules(tmp_path, filename, payload):
    rules_file = tmp_path / filename
    rules_file.write_text(json.dumps(payload), encoding="utf-8")
    return rules_file


def _base_rule_payload():
    return {
        "metadata": {"name": "base", "priority": 0},
        "default": {
            "segments": ["slug", "region"],
            "max_length": 64,
            "require_sanmar_prefix": False,
        },
        "resources": {
            "storage_account": {
                "segments": ["slug", "region", "environment"],
                "max_length": 24,
            }
        },
    }


def test_provider_merges_layers_by_priority(tmp_path):
    _write_rules(tmp_path, "base.json", _base_rule_payload())
    overlay = {
        "metadata": {"name": "overlay", "priority": 10},
        "resources": {
            "storage_account": {
                "max_length": 30,
                "require_sanmar_prefix": True,
                "validators": {
                    "allowed_values": {"region": ["wus", "wus2"]}
                },
            }
        },
    }
    _write_rules(tmp_path, "overlay.json", overlay)

    provider = JsonRuleProvider(rules_path=tmp_path)

    storage_rule = provider.get_rule("storage_account")
    assert storage_rule.max_length == 30
    assert storage_rule.require_sanmar_prefix is True
    assert list(storage_rule.segments) == ["slug", "region", "environment"]
    assert storage_rule.validators  # validators merged

    # Unknown resources fall back to the merged default
    default_rule = provider.get_rule("default")
    assert provider.get_rule("unknown") is default_rule


def test_provider_skips_disabled_layers(tmp_path):
    _write_rules(tmp_path, "base.json", _base_rule_payload())
    disabled = {
        "metadata": {"name": "disabled", "priority": 999, "enabled": False},
        "default": {"max_length": 10},
    }
    _write_rules(tmp_path, "disabled.json", disabled)

    provider = JsonRuleProvider(rules_path=tmp_path)
    assert provider.get_rule("default").max_length == 64


def test_provider_builds_declarative_validators(tmp_path):
    _write_rules(tmp_path, "base.json", _base_rule_payload())
    strict = {
        "metadata": {"name": "strict", "priority": 50},
        "resources": {
            "storage_account": {
                "validators": {
                    "allowed_values": {
                        "region": ["wus", "wus2"],
                        "environment": ["prd"],
                    },
                    "required": ["region", "environment"],
                    "require_any": {
                        "system": ["system", "system_short"],
                    },
                }
            }
        },
    }
    _write_rules(tmp_path, "strict.json", strict)

    provider = JsonRuleProvider(rules_path=tmp_path)
    rule = provider.get_rule("storage_account")

    valid_payload = {
        "region": "wus",
        "environment": "prd",
        "system_short": "erp",
    }
    # Should not raise
    rule.validate_payload(valid_payload)

    with pytest.raises(ValueError):
        rule.validate_payload({"region": "uks", "environment": "prd", "system_short": "erp"})

    with pytest.raises(ValueError):
        rule.validate_payload({"region": "wus", "environment": "prd"})


def test_provider_requires_default_across_layers(tmp_path):
    overlay = {
        "metadata": {"name": "overlay", "priority": 10},
        "resources": {"alpha": {"segments": ["slug"]}},
    }
    _write_rules(tmp_path, "overlay.json", overlay)

    with pytest.raises(ValueError):
        JsonRuleProvider(rules_path=tmp_path)


def test_provider_reload_picks_up_directory_changes(tmp_path):
    base = _base_rule_payload()
    _write_rules(tmp_path, "base.json", base)

    provider = JsonRuleProvider(rules_path=tmp_path)
    assert provider.get_rule("default").max_length == 64

    updated_base = _base_rule_payload()
    updated_base["default"]["max_length"] = 80
    _write_rules(tmp_path, "base.json", updated_base)

    provider.reload()
    assert provider.get_rule("default").max_length == 80


def test_provider_accepts_single_file(tmp_path):
    payload = {
        "default": {"segments": ["slug"], "max_length": 50},
        "resources": {},
    }
    rules_file = _write_rules(tmp_path, "rules.json", payload)

    provider = JsonRuleProvider(rules_path=rules_file)
    assert provider.get_rule("default").max_length == 50


@pytest.mark.parametrize("invalid", [None, 123, "text"])
def test_provider_rejects_invalid_resource_config(tmp_path, invalid):
    payload = {
        "default": {"segments": ["slug"], "max_length": 10},
        "resources": {"alpha": invalid},
    }
    rules_file = _write_rules(tmp_path, "rules.json", payload)

    with pytest.raises(ValueError):
        JsonRuleProvider(rules_path=rules_file)
