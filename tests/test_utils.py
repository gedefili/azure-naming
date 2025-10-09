import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import name_generator, naming_rules, validation


def test_load_naming_rule_default():
    rule = naming_rules.load_naming_rule("virtual_machine")
    assert rule == naming_rules.DEFAULT_RULE


def test_load_naming_rule_specific():
    rule = naming_rules.load_naming_rule("storage_account")
    assert rule.max_length == 24
    assert rule.require_sanmar_prefix is True
    assert any(field.key == "name" for field in rule.display_fields)


def test_build_name_composes_segments():
    rule = naming_rules.DEFAULT_RULE
    name = name_generator.build_name(
        region="wus2",
        environment="prod",
        slug="st",
        rule=rule,
        optional_inputs={
            "system_short": "erp",
            "domain": "fin",
            "subdomain": "pay",
            "index": "01",
        },
    )
    assert name == "st-erp-fin-pay-prod-wus2-01"


def test_build_name_adds_prefix_when_required():
    rule = naming_rules.load_naming_rule("storage_account")
    name = name_generator.build_name(
        region="wus2",
        environment="prod",
        slug="st",
        rule=rule,
        optional_inputs={},
    )
    assert name == "sanmar-st-prod-wus2"


def test_validate_name_success():
    rule = {"max_length": 20}
    validation.validate_name("valid-name", rule)


def test_validate_name_length():
    rule = {"max_length": 5}
    with pytest.raises(ValueError):
        validation.validate_name("toolongname", rule)


def test_validate_name_lowercase():
    rule = {"max_length": 20}
    with pytest.raises(ValueError):
        validation.validate_name("Invalid", rule)


def test_validate_name_characters():
    rule = {"max_length": 20}
    with pytest.raises(ValueError):
        validation.validate_name("no_good$", rule)


def test_render_display_skips_optional_missing_values():
    rule = naming_rules.DEFAULT_RULE
    payload = {
        "name": "sanmar-st-dev-wus2",
        "resourceType": "storage_account",
        "region": "wus2",
        "environment": "dev",
        "slug": "st",
    }

    display = rule.render_display(payload)
    keys = [item["key"] for item in display]

    assert "name" in keys
    assert "project" not in keys


def test_render_display_includes_required_fields():
    rule = naming_rules.load_naming_rule("storage_account")
    payload = {
        "name": "sanmar-st-dev-wus2",
        "resourceType": "storage_account",
        "region": "wus2",
        "environment": "dev",
        "slug": "st",
        "project": "finance",
    }

    display = rule.render_display(payload)
    entry = next(item for item in display if item["key"] == "name")
    assert entry["label"] == "Storage Account Name"
    assert entry["value"] == "sanmar-st-dev-wus2"


class StaticRuleProvider:
    def __init__(self, rule):
        self.rule = rule

    def get_rule(self, resource_type: str):
        return self.rule


def test_custom_rule_provider():
    original_provider = naming_rules.get_rule_provider()
    custom_rule = naming_rules.NamingRule(
        segments=("slug", "environment"),
        max_length=10,
        require_sanmar_prefix=False,
    )
    provider = StaticRuleProvider(custom_rule)
    try:
        naming_rules.set_rule_provider(provider)
        assert naming_rules.load_naming_rule("any") is custom_rule
    finally:
        naming_rules.set_rule_provider(original_provider)
