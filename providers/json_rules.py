"""Naming rule provider that loads definitions from JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

from core.naming_rules import DisplayField, NamingRule, NamingRuleProvider


@dataclass(slots=True)
class _RuleLayer:
    path: Path
    priority: int
    enabled: bool
    name: str
    default_config: Mapping[str, Any] | None
    resources_config: Dict[str, Mapping[str, Any]]


class JsonRuleProvider(NamingRuleProvider):
    """Load naming rules from one or more JSON configuration files."""

    def __init__(
        self,
        *,
        rules_path: str | Path,
    ) -> None:
        self._path = Path(rules_path)
        if not self._path.exists():
            raise FileNotFoundError(f"Naming rules path '{self._path}' does not exist.")
        self._default_rule: NamingRule | None = None
        self._resource_rules: Dict[str, NamingRule] = {}
        self.reload()

    def reload(self) -> None:
        """Reload rule definitions from disk."""

        layers = _load_rule_layers(self._path)
        if not layers:
            raise ValueError(f"No enabled rule layers found under '{self._path}'.")

        default_rule: NamingRule | None = None
        resource_rules: Dict[str, NamingRule] = {}

        for layer in layers:
            if layer.default_config:
                default_rule = _to_rule(layer.default_config, fallback_rule=default_rule)
            if default_rule is None:
                raise ValueError(
                    f"Rule layer '{layer.path}' defines resources before any default rule is available."
                )

            for key, config in layer.resources_config.items():
                normalised = str(key).lower()
                base_rule = resource_rules.get(normalised, default_rule)
                rule = _to_rule(config, fallback_rule=base_rule)
                resource_rules[normalised] = rule

        if default_rule is None:
            raise ValueError("At least one rule layer must define a default rule.")

        self._default_rule = default_rule
        self._resource_rules = resource_rules

    def get_rule(self, resource_type: str) -> NamingRule:
        if self._default_rule is None:
            raise RuntimeError("Naming rules have not been loaded.")
        key = resource_type.lower()
        if key in self._resource_rules:
            return self._resource_rules[key]
        if key in {"default", "__default__"}:
            return self._default_rule
        return self._default_rule

    def list_resource_types(self) -> Sequence[str]:
        keys = set(self._resource_rules.keys())
        keys.add("default")
        return tuple(sorted(keys))

    def export_resource_rules(self) -> Dict[str, NamingRule]:
        """Return a copy of resource-specific rules for inspection."""

        return dict(self._resource_rules)


def _to_display_fields(config: Iterable[Mapping[str, object]] | None) -> Sequence[DisplayField]:
    fields: list[DisplayField] = []
    for item in config or []:
        key = str(item.get("key"))
        label = str(item.get("label", key.replace("_", " ").title()))
        description = item.get("description")
        optional = bool(item.get("optional", True))
        fields.append(
            DisplayField(
                key=key,
                label=label,
                description=str(description) if description else None,
                optional=optional,
            )
        )
    return tuple(fields)


def _to_rule(
    config: Mapping[str, object], *, fallback_rule: NamingRule | None
) -> NamingRule:
    segments_value = config.get("segments")
    if segments_value:
        segments = tuple(str(segment) for segment in segments_value)
    elif fallback_rule is not None:
        segments = tuple(fallback_rule.segments)
    else:
        raise ValueError("Rule definition must provide 'segments'.")

    if "max_length" in config:
        max_length = int(config.get("max_length", 0))
    elif fallback_rule is not None:
        max_length = fallback_rule.max_length
    else:
        max_length = 80

    if "require_sanmar_prefix" in config:
        require_prefix = bool(config.get("require_sanmar_prefix", False))
    elif fallback_rule is not None:
        require_prefix = fallback_rule.require_sanmar_prefix
    else:
        require_prefix = False

    display_config = config.get("display")
    if display_config is not None:
        display_fields = _to_display_fields(display_config)
    elif fallback_rule is not None:
        display_fields = fallback_rule.display_fields
    else:
        display_fields = ()

    validators_config = config.get("validators") if isinstance(config, Mapping) else None
    validators = _build_validators(validators_config)
    if not validators and fallback_rule is not None:
        validators = fallback_rule.validators

    name_template = config.get("name_template")
    if name_template is None and fallback_rule is not None:
        name_template = fallback_rule.name_template

    summary_template = config.get("summary_template")
    if summary_template is None and fallback_rule is not None:
        summary_template = fallback_rule.summary_template

    return NamingRule(
        segments=segments,
        max_length=max_length,
        require_sanmar_prefix=require_prefix,
        display_fields=display_fields,
        validators=validators,
        name_template=str(name_template) if name_template else None,
        summary_template=str(summary_template) if summary_template else None,
    )


def _load_rule_layers(path: Path) -> list[_RuleLayer]:
    if path.is_dir():
        candidates = sorted(file for file in path.glob("*.json") if file.is_file())
        layers = [_parse_rule_layer(candidate) for candidate in candidates]
    else:
        layers = [_parse_rule_layer(path)]

    enabled_layers = [layer for layer in layers if layer.enabled]
    enabled_layers.sort(key=lambda layer: (layer.priority, layer.path.name))
    return enabled_layers


def _parse_rule_layer(path: Path) -> _RuleLayer:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"Rule file '{path}' must contain a JSON object at the top level.")

    metadata = data.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise ValueError(f"Rule file '{path}' must contain an object for 'metadata'.")

    priority = int(metadata.get("priority", 0))
    enabled = bool(metadata.get("enabled", True))
    name = str(metadata.get("name") or path.stem)

    default_config = data.get("default")
    if default_config is not None and not isinstance(default_config, Mapping):
        raise ValueError(f"'default' in '{path}' must be an object when provided.")

    resources_config_raw = data.get("resources") or {}
    if not isinstance(resources_config_raw, Mapping):
        raise ValueError(f"'resources' in '{path}' must be an object mapping resource types to definitions.")

    resources_config: Dict[str, Mapping[str, Any]] = {}
    for key, value in resources_config_raw.items():
        if not isinstance(value, Mapping):
            raise ValueError(f"Rule definition for '{key}' in '{path}' must be an object.")
        resources_config[str(key).lower()] = value

    return _RuleLayer(
        path=path,
        priority=priority,
        enabled=enabled,
        name=name,
        default_config=default_config,
        resources_config=resources_config,
    )


def _build_validators(config: Mapping[str, object] | None) -> Sequence[Callable[[Mapping[str, object]], None]]:
    if not config:
        return ()

    validators: list[Callable[[Mapping[str, object]], None]] = []

    allowed_values = config.get("allowed_values")
    if isinstance(allowed_values, Mapping):
        validators.append(_make_allowed_values_validator(allowed_values))

    required_fields = config.get("required")
    if isinstance(required_fields, Iterable) and not isinstance(required_fields, (str, bytes)):
        validators.append(_make_required_fields_validator(required_fields))

    require_any = config.get("require_any")
    if isinstance(require_any, Mapping):
        validators.append(_make_require_any_validator(require_any))

    return tuple(validators)


def _make_allowed_values_validator(config: Mapping[str, object]) -> Callable[[Mapping[str, object]], None]:
    normalised: Dict[str, set[str]] = {}
    for field, values in config.items():
        if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
            raise ValueError("'allowed_values' entries must be arrays of strings.")
        normalised[str(field)] = {
            str(value).lower().strip() for value in values if str(value).strip()
        }

    def validator(payload: Mapping[str, object]) -> None:
        for field, allowed in normalised.items():
            raw = payload.get(field)
            if raw is None:
                continue
            value = str(raw).lower().strip()
            if value not in allowed:
                raise ValueError(f"{field} must be one of {sorted(allowed)}")

    return validator


def _make_required_fields_validator(fields: Iterable[object]) -> Callable[[Mapping[str, object]], None]:
    required = [str(field) for field in fields]

    def validator(payload: Mapping[str, object]) -> None:
        for field in required:
            raw = payload.get(field)
            if not _has_value(raw):
                raise ValueError(f"{field} is required for this resource type")

    return validator


def _make_require_any_validator(config: Mapping[str, object]) -> Callable[[Mapping[str, object]], None]:
    groups: Dict[str, tuple[str, ...]] = {}
    for label, options in config.items():
        if not isinstance(options, Iterable) or isinstance(options, (str, bytes)):
            raise ValueError("'require_any' entries must be arrays of field names.")
        fields = tuple(str(option) for option in options)
        if not fields:
            raise ValueError("'require_any' groups must contain at least one field name.")
        groups[str(label)] = fields

    def validator(payload: Mapping[str, object]) -> None:
        for label, options in groups.items():
            if any(_has_value(payload.get(option)) for option in options):
                continue
            joined = ", ".join(options)
            raise ValueError(f"One of ({joined}) must be provided for '{label}'.")

    return validator


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def load_provider_from_json(path: str | Path) -> JsonRuleProvider:
    """Convenience helper for environment-driven configuration."""

    return JsonRuleProvider(rules_path=path)
