import json
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import slug as slug_adapter
from adapters import slug_loader
from core import name_generator, naming_rules, slug_service, validation
from app.routes.docs import _normalise_openapi_spec


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
            "system": "erp",
            "subsystem": "pay",
            "index": "01",
        },
    )
    # Format: {region}-{environment}-{slug}-{system}{subsystem_segment}{index_segment}
    assert name == "wus2-prod-st-erp-pay-01"


def test_build_name_adds_prefix_when_required():
    rule = naming_rules.load_naming_rule("storage_account")
    name = name_generator.build_name(
        region="wus2",
        environment="prod",
        slug="st",
        rule=rule,
        optional_inputs={"system": "sn"},
    )
    # Template: {region}{environment}{slug}{sanmar_prefix}{system}{subsystem}{index}
    assert name == "wus2prodstsanmarsn"


def test_build_name_uses_template_when_defined():
    rule = naming_rules.NamingRule(
        segments=("slug", "region"),
        max_length=50,
        name_template="{slug}-{region}{index_segment}",
    )
    name = name_generator.build_name(
        region="wus2",
        environment="prod",
        slug="st",
        rule=rule,
        optional_inputs={"index": "01"},
    )
    assert name == "st-wus2-01"


def test_render_summary_uses_template():
    rule = naming_rules.NamingRule(
        segments=("slug",),
        max_length=50,
        summary_template="Name {name} in {environment_upper}-{region_upper}",
    )
    payload = {
        "name": "resource",
        "environment": "dev",
        "region": "wus2",
    }
    summary = rule.render_summary(payload)
    assert summary == "Name resource in DEV-WUS2"


def test_normalise_openapi_spec_hoists_defs():
    raw = {
        "openapi": "3.0.0",
        "paths": {
            "/example": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$defs": {
                                            "Thing": {
                                                "type": "object",
                                                "properties": {"name": {"type": "string"}},
                                            }
                                        },
                                        "properties": {
                                            "item": {
                                                "$ref": "#/$defs/Thing"
                                            }
                                        },
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    normalised = json.loads(_normalise_openapi_spec(json.dumps(raw)))
    ref = normalised["paths"]["/example"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["item"]["$ref"]
    assert ref == "#/components/schemas/Thing"
    assert normalised["components"]["schemas"]["Thing"]["type"] == "object"


def test_normalise_openapi_spec_sets_server_base_path():
    raw = {
        "openapi": "3.0.0",
        "paths": {},
    }

    normalised = json.loads(_normalise_openapi_spec(json.dumps(raw)))
    assert {"url": "/api"} in normalised["servers"]


def test_get_slug_supports_space_and_underscore_variants(monkeypatch):
    class FakeTable:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def query_entities(self, query_filter: str):
            self.queries.append(query_filter)
            # Current implementation uses canonical form (underscores)
            if "FullName eq 'resource_group'" in query_filter:
                return [{"Slug": "rg"}]
            return []

    fake_table = FakeTable()
    monkeypatch.setattr(slug_adapter, "get_table_client", lambda _: fake_table)

    assert slug_adapter.get_slug("resource group") == "rg"
    assert any("FullName eq 'resource_group'" in query for query in fake_table.queries)


def test_sync_slug_definitions_stores_canonical_and_human_names(monkeypatch):
    inserted: list[dict[str, str]] = []

    class FakeTable:
        def upsert_entity(self, *, mode: str, entity: dict[str, str]) -> None:  # pragma: no cover - simple stub
            inserted.append(entity)

    monkeypatch.setattr(slug_loader, "get_all_remote_slugs", lambda: {"rg": "resource_group"})
    monkeypatch.setattr(slug_loader, "get_table_client", lambda _: FakeTable())

    updated = slug_loader.sync_slug_definitions()

    assert updated == 1
    assert inserted[0]["ResourceType"] == "resource_group"
    assert inserted[0]["FullName"] == "resource group"


def test_slug_service_can_register_custom_provider(monkeypatch):
    original = slug_service.get_slug_providers()

    class DummyProvider:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_slug(self, resource_type: str) -> str:
            self.calls.append(resource_type)
            if resource_type == "custom":
                return "cs"
            raise ValueError("Not found")

    dummy = DummyProvider()
    slug_service.set_slug_providers([dummy])

    try:
        assert slug_service.get_slug("custom") == "cs"
        assert dummy.calls == ["custom"]
    finally:
        slug_service.set_slug_providers(original)


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

    def list_resource_types(self):
        return ("any",)


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


def test_describe_rule_exposes_template_details():
    original_provider = naming_rules.get_rule_provider()
    custom_rule = naming_rules.NamingRule(
        segments=("slug", "system_short", "environment", "region"),
        max_length=30,
        require_sanmar_prefix=True,
        name_template="{slug}-{system_short}{index_segment}-{environment}-{region}",
        display_fields=(
            naming_rules.DisplayField(key="name", label="Name", optional=False),
            naming_rules.DisplayField(key="system", label="System"),
        ),
    )
    provider = StaticRuleProvider(custom_rule)

    try:
        naming_rules.set_rule_provider(provider)
        spec = naming_rules.describe_rule("any")
        assert spec["nameTemplate"] == custom_rule.name_template
        assert any(field["name"] == "index_segment" for field in spec["templateFields"])
        assert any(mapping["segment"] == "system_short" for mapping in spec["segmentMappings"])
    finally:
        naming_rules.set_rule_provider(original_provider)


def test_list_resource_types_includes_default():
    types = naming_rules.list_resource_types()
    assert "default" in types
