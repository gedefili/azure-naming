import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from utils import naming_rules, name_generator, validation


def test_load_naming_rule_default():
    rule = naming_rules.load_naming_rule("virtual_machine")
    assert rule == naming_rules.DEFAULT_RULE


def test_load_naming_rule_specific():
    rule = naming_rules.load_naming_rule("storage_account")
    assert rule["max_length"] == 24
    assert rule["require_sanmar_prefix"] is True


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
