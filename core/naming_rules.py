# File: core/naming_rules.py
# Version: 1.0.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Provides simple loader for resource naming rules.
"""Simple loader for resource naming rules."""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Callable, Dict, List, Mapping, Optional, Protocol, Sequence


class _SafeFormatDict(dict):
    """Dict that returns an empty string when formatting misses a key."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return ""


def _normalise_context(context: Mapping[str, object]) -> _SafeFormatDict:
    normalised: Dict[str, str] = {}
    for key, value in context.items():
        if isinstance(value, str):
            normalised[key] = value
        elif value is None:
            normalised[key] = ""
        else:
            normalised[key] = str(value)
    return _SafeFormatDict(normalised)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisplayField:
    """Describes how to present a field in the response payload."""

    key: str
    label: str
    description: Optional[str] = None
    optional: bool = True

    def to_dict(self) -> Dict[str, object]:  # pragma: no cover - trivial
        data: Dict[str, object] = {
            "key": self.key,
            "label": self.label,
            "optional": self.optional,
        }
        if self.description:
            data["description"] = self.description
        return data


@dataclass(frozen=True)
class NamingRule:
    """Immutable representation of a naming rule."""

    segments: Sequence[str]
    max_length: int
    require_sanmar_prefix: bool = False
    display_fields: Sequence[DisplayField] = ()
    validators: Sequence[Callable[[Mapping[str, object]], None]] = ()
    name_template: Optional[str] = None
    summary_template: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "segments": list(self.segments),
            "max_length": self.max_length,
            "require_sanmar_prefix": self.require_sanmar_prefix,
            "display_fields": [field.to_dict() for field in self.display_fields],
            "name_template": self.name_template,
            "summary_template": self.summary_template,
        }

    def validate_payload(self, payload: Mapping[str, object]) -> None:
        for validator in self.validators:
            validator(payload)

    def render_display(self, payload: Mapping[str, object]) -> List[Dict[str, object]]:
        """Create an ordered view of response fields for end-user presentation."""

        formatted: List[Dict[str, object]] = []
        for field in self.display_fields:
            raw_value = payload.get(field.key) if isinstance(payload, Mapping) else None
            if raw_value is None and field.optional:
                continue
            entry: Dict[str, object] = {
                "key": field.key,
                "label": field.label,
                "value": None if raw_value is None else str(raw_value),
            }
            if field.description:
                entry["description"] = field.description
            formatted.append(entry)
        return formatted

    def render_summary(self, payload: Mapping[str, object]) -> Optional[str]:
        if not self.summary_template:
            return None
        context = _normalise_context(payload)
        for key in ("environment", "region", "system", "resourceType"):
            value = context.get(key, "")
            context[f"{key}_upper"] = value.upper()
            context[f"{key}_title"] = value.title()
        return self.summary_template.format_map(context)


class NamingRuleProvider(Protocol):
    """Contract for pluggable naming rule providers."""

    def get_rule(self, resource_type: str) -> NamingRule:
        """Return a naming rule for the given resource type."""

    def list_resource_types(self) -> Sequence[str]:
        """Enumerate resource types with explicit rule definitions."""


class DictionaryRuleProvider:
    """In-memory provider useful for tests and composed providers."""

    def __init__(
        self,
        default_rule: NamingRule,
        resource_rules: Mapping[str, NamingRule],
    ) -> None:
        self._default_rule = default_rule
        self._resource_rules = {key.lower(): rule for key, rule in resource_rules.items()}

    def get_rule(self, resource_type: str) -> NamingRule:  # pragma: no cover - trivial
        key = resource_type.lower()
        if key in {"default", "__default__"}:
            return self._default_rule
        return self._resource_rules.get(key, self._default_rule)

    def list_resource_types(self) -> Sequence[str]:  # pragma: no cover - simple getter
        keys = set(self._resource_rules.keys())
        keys.add("default")
        return tuple(sorted(keys))


_RULES_PATH_ENV = "NAMING_RULES_PATH"
_LEGACY_RULES_FILE_ENV = "NAMING_RULES_FILE"


def _resolve_rules_path() -> Path:
    override = os.environ.get(_RULES_PATH_ENV) or os.environ.get(_LEGACY_RULES_FILE_ENV)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "rules"


def _load_default_provider() -> NamingRuleProvider:
    from providers.json_rules import JsonRuleProvider  # Local import to avoid circular dependency

    return JsonRuleProvider(rules_path=_resolve_rules_path())


def _sync_shared_state(provider: NamingRuleProvider) -> None:
    global DEFAULT_RULE, RESOURCE_RULES

    DEFAULT_RULE = provider.get_rule("default")
    resource_rules: Dict[str, NamingRule] = {}
    if hasattr(provider, "list_resource_types"):
        for resource_type in provider.list_resource_types():
            normalised = str(resource_type).lower()
            if normalised in {"default", "__default__"}:
                continue
            resource_rules[normalised] = provider.get_rule(normalised)
    RESOURCE_RULES = resource_rules


_TEMPLATE_FORMATTER = Formatter()


def _extract_template_fields(template: str) -> List[Dict[str, str]]:
    fields: List[Dict[str, str]] = []
    seen: set[str] = set()
    for _, field_name, _, _ in _TEMPLATE_FORMATTER.parse(template):
        if not field_name or field_name in seen:
            continue
        seen.add(field_name)
        entry: Dict[str, str] = {"name": field_name}
        if field_name.endswith("_segment"):
            entry["type"] = "optionalSegment"
            entry["variantOf"] = field_name[: -len("_segment")]
        elif field_name in {"region", "environment", "slug"}:
            entry["type"] = "coreInput"
        else:
            entry["type"] = "context"
        fields.append(entry)
    return fields


_SEGMENT_ALIAS_HINTS: Dict[str, Sequence[str]] = {
    "system_short": ("system", "system_short"),
    "index": ("index",),
}


def _build_segment_mappings(rule: NamingRule) -> List[Dict[str, object]]:
    mappings: List[Dict[str, object]] = []
    for segment in rule.segments:
        entry: Dict[str, object] = {"segment": segment}
        if segment == "slug":
            entry["source"] = "derived"
            entry["description"] = "Slug generated from the resource type via slug providers."
        elif segment in {"region", "environment"}:
            entry["source"] = "payload"
            entry["aliases"] = (segment,)
        else:
            entry["source"] = "payload"
            entry["aliases"] = _SEGMENT_ALIAS_HINTS.get(segment, (segment,))
        mappings.append(entry)
    return mappings


_provider: NamingRuleProvider = _load_default_provider()
DEFAULT_RULE: NamingRule
RESOURCE_RULES: Dict[str, NamingRule]


def _load_provider_from_env() -> Optional[NamingRuleProvider]:
    provider_path = os.environ.get("NAMING_RULE_PROVIDER")
    if not provider_path:
        return None

    try:
        module_path, _, attr_name = provider_path.rpartition(".")
        if not module_path or not attr_name:
            raise ValueError("NAMING_RULE_PROVIDER must be in 'module.attr' format")

        module = importlib.import_module(module_path)
        factory = getattr(module, attr_name)
        provider = factory() if callable(factory) else factory
        if not hasattr(provider, "get_rule"):
            raise TypeError("Provider must define a 'get_rule' method")
        return provider  # type: ignore[return-value]
    except Exception:  # pragma: no cover - defensive logging only
        logger.exception("Failed to load naming rule provider from environment")
        return None


_env_provider = _load_provider_from_env()
if _env_provider:
    _provider = _env_provider

_sync_shared_state(_provider)


def set_rule_provider(provider: NamingRuleProvider) -> None:
    """Override the active naming rule provider at runtime."""

    global _provider
    _provider = provider
    _sync_shared_state(_provider)


def get_rule_provider() -> NamingRuleProvider:
    """Return the currently active naming rule provider."""

    return _provider


def load_naming_rule(resource_type: str) -> NamingRule:
    """Return the naming rule for the requested resource type."""

    return _provider.get_rule(resource_type)


def list_resource_types(include_default: bool = True) -> Sequence[str]:
    """Return the known resource types exposed by the active provider."""

    provider = get_rule_provider()
    resource_types: List[str] = []
    if hasattr(provider, "list_resource_types"):
        resource_types.extend(str(rt).lower() for rt in provider.list_resource_types())
    if include_default and "default" not in resource_types:
        resource_types.insert(0, "default")
    # Preserve order while removing duplicates
    seen: set[str] = set()
    ordered: List[str] = []
    for item in resource_types:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return tuple(ordered)


def describe_rule(resource_type: str) -> Dict[str, object]:
    """Provide a user-friendly JSON-compatible description of a naming rule."""

    normalised = resource_type.lower()
    available = set(list_resource_types(include_default=True))
    if normalised not in available:
        raise KeyError(f"Unknown resource type '{resource_type}'. Known types: {sorted(available)}")

    lookup_type = "__default__" if normalised == "default" else normalised
    rule = load_naming_rule(lookup_type)

    payload_required = ["resourceType", "region", "environment"]
    segment_mappings = _build_segment_mappings(rule)
    optional_aliases: set[str] = set()
    for mapping in segment_mappings:
        if mapping.get("source") == "payload" and mapping["segment"] not in {"region", "environment"}:
            optional_aliases.update(mapping.get("aliases", []))

    template_fields = []
    if rule.name_template:
        template_fields = _extract_template_fields(rule.name_template)

    description: Dict[str, object] = {
        "resourceType": normalised,
        "maxLength": rule.max_length,
        "requireSanmarPrefix": rule.require_sanmar_prefix,
        "segments": list(rule.segments),
        "optionalSegments": [segment for segment in rule.segments if segment not in {"slug", "region", "environment"}],
        "displayFields": [field.to_dict() for field in rule.display_fields],
        "nameTemplate": rule.name_template,
        "summaryTemplate": rule.summary_template,
        "templateFields": template_fields,
        "segmentMappings": segment_mappings,
        "payloadInputs": {
            "required": payload_required,
            "optional": sorted(optional_aliases),
        },
    }

    return description
