"""US-centric naming rule provider with stricter validation."""

from __future__ import annotations

from typing import Mapping

from core import naming_rules
from core.naming_rules import DisplayField, DictionaryRuleProvider, NamingRule

_ALLOWED_REGIONS = {"wus", "wus2", "eus", "eus1"}
_ALLOWED_ENVIRONMENTS = {"prd", "stg", "tst", "uat", "alt"}


class USStrictRuleProvider:
    """Rule provider that enforces stricter validation for storage accounts."""

    def __init__(self, base: naming_rules.NamingRuleProvider | None = None) -> None:
        self._base = base or DictionaryRuleProvider(
            naming_rules.DEFAULT_RULE,
            naming_rules.RESOURCE_RULES,
        )
        self._storage_rule = NamingRule(
            segments=("slug", "system_short", "subdomain", "environment", "region", "index"),
            max_length=24,
            require_sanmar_prefix=True,
            display_fields=(
                DisplayField(key="name", label="Storage Account Name", optional=False),
                DisplayField(key="resourceType", label="Resource Type", optional=False),
                DisplayField(key="slug", label="Slug", optional=False),
                DisplayField(key="environment", label="Environment", optional=False),
                DisplayField(key="region", label="Region", optional=False),
                DisplayField(key="project", label="Project"),
                DisplayField(key="purpose", label="Subsystem"),
                DisplayField(key="system", label="System", optional=False),
                DisplayField(key="index", label="Index"),
            ),
            validators=(self._validate_storage_payload,),
            name_template="{region}-{environment}-{slug}-{system_short}{index_segment}",
            summary_template="Storage account '{name}' for system '{system_upper}' in {environment_upper}-{region_upper}",
        )

    def _validate_storage_payload(self, payload: Mapping[str, object]) -> None:
        region = str(payload.get("region") or "").lower()
        if region not in _ALLOWED_REGIONS:
            raise ValueError(f"region must be one of {sorted(_ALLOWED_REGIONS)}")

        environment = str(payload.get("environment") or "").lower()
        if environment not in _ALLOWED_ENVIRONMENTS:
            raise ValueError(f"environment must be one of {sorted(_ALLOWED_ENVIRONMENTS)}")

        system = payload.get("system") or payload.get("system_short")
        if not system:
            raise ValueError("system is required for this resource type")

        subsystem = payload.get("purpose") or payload.get("subdomain")
        if not subsystem:
            raise ValueError("subsystem (purpose/subdomain) is required for this resource type")

    def get_rule(self, resource_type: str) -> NamingRule:
        if resource_type.lower() == "storage_account":
            return self._storage_rule
        return self._base.get_rule(resource_type)


def get_provider() -> USStrictRuleProvider:
    """Factory used by the NAMING_RULE_PROVIDER environment variable."""

    return USStrictRuleProvider()
