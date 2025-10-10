# 🗃 Table Schemas & Naming Rules

This document explains the structure of the Azure Table Storage tables and the logic used to generate SanMar-compliant Azure resource names.

---

## 📁 Tables Used

### 1. `ClaimedNames`

Tracks all currently claimed names.

| Property       | Type     | Description                            |
| -------------- | -------- | -------------------------------------- |
| `PartitionKey` | string   | Always `claimed`                       |
| `RowKey`       | string   | The generated name                     |
| `ResourceType` | string   | E.g., `storage_account`                |
| `Slug`         | string   | The assigned short form, e.g., `st`    |
| `Project`      | string   | Project identifier                     |
| `Purpose`      | string   | Purpose or function of the resource    |
| `Environment`  | string   | E.g., `dev`, `prod`                    |
| `Region`       | string   | Azure region short name (e.g., `wus2`) |
| `ClaimedBy`    | string   | Email or UPN of the claimant           |
| `ClaimedAt`    | ISO 8601 | UTC timestamp                          |
| `Released`     | bool     | If true, the name is no longer in use  |
| `ReleasedAt`   | ISO 8601 | Timestamp when released (if any)       |

---

### 2. `AuditLogs`

Tracks all claims and releases for auditing.

| Property       | Type     | Description                         |
| -------------- | -------- | ----------------------------------- |
| `PartitionKey` | string   | The name (`RowKey` in ClaimedNames) |
| `RowKey`       | string   | A UUID or timestamp ID              |
| `User`         | string   | Who performed the operation         |
| `Action`       | string   | `claimed` or `released`             |
| `Timestamp`    | ISO 8601 | UTC timestamp                       |
| `Note`         | string   | Optional contextual message         |

---

### 3. `SlugMappings`

Pulled from the [Azure terraform-azurerm-naming](https://github.com/Azure/terraform-azurerm-naming) project.

| Property       | Type     | Description                                  |
| -------------- | -------- | -------------------------------------------- |
| `PartitionKey` | string   | Always `slug`                                |
| `RowKey`       | string   | The short slug (e.g., `st`)                  |
| `Slug`         | string   | Duplicate of `RowKey`                        |
| `ResourceType` | string   | Canonical identifier (e.g., `storage_account`) |
| `FullName`     | string   | Human-readable label (e.g., `storage account`) |
| `Source`       | string   | Origin of the mapping (e.g., `azure_defined_specs`) |
| `UpdatedAt`    | ISO 8601 | When last updated                            |

---

## 🧪 Naming Rule Logic

A valid name must:

* Be all lowercase
* Use only hyphens (no underscores or dots)
* Follow length constraints (e.g., storage accounts ≤ 24 chars)
* Use the correct **slug** for the resource type
* Include `sanmar` for globally unique resources (e.g., storage accounts)

### Format Example:

```
<slug>-sanmar-<project>-<purpose>-<env>-<region>
```

> Example: `st-sanmar-finance-costreports-dev-wus2`

### 🔌 Custom Rule Providers

Rules are supplied through a pluggable provider interface so you can swap in new storage mechanisms without touching the generation pipeline.

* **Default source:** In-memory definitions from `DEFAULT_RULE_CONFIG` and `RESOURCE_RULE_CONFIG` within `core/naming_rules.py`.
* **Bundled override:** At startup the application also wires in `providers.us_rules.get_provider()` (exposed as *USStrictRuleProvider*) to apply SanMar’s US-centric constraints.
* **Override at runtime:** Export `NAMING_RULE_PROVIDER` with a dotted path (for example `my_package.rules:get_provider`). The referenced attribute should return an object that exposes `get_rule(resource_type) -> NamingRule`.
* **Programmatic swap:** Call `core.naming_rules.set_rule_provider(...)` during startup to inject a custom provider.

Each provider returns a `NamingRule` object describing segments, maximum length, prefix requirements, and the preferred presentation layout for response payloads. The name generator and validator consume this contract only, keeping rule evaluation and user-facing responses decoupled from where or how rules are stored.

#### Example: Enforcing US-only Regions

```bash
export NAMING_RULE_PROVIDER="providers.us_rules.get_provider"
```

The bundled `USStrictRuleProvider` overrides the storage account rule so that:

* `region` must be one of `wus`, `wus2`, `eus`, or `eus1`.
* `environment` must be one of `prd`, `stg`, `tst`, `uat`, or `alt`.
* `system` and `purpose`/`subdomain` values are required to build the name.
* Other metadata (project, index, etc.) remains optional.

Any violation raises a validation error before a name is generated, producing a `400 Bad Request` response from the API.

### Extending with New Rules

1. Create a module that exposes either a provider class with `get_rule(resource_type) -> NamingRule` or a factory function that returns such an object (see `providers/us_rules.py` for a working example).
2. Register the provider by setting `NAMING_RULE_PROVIDER="your.module:get_provider"` or by calling `core.naming_rules.set_rule_provider(...)` during startup.
3. (Optional) Layer the new provider with the existing ones by returning a sequence from your factory if you want to keep the US rules alongside custom logic.
4. Update automated tests and documentation to reflect the new rule behavior.

---

## 🔌 Slug Provider Pipeline

Slug resolution is handled by `core.slug_service`, which fans out through a chain of providers. Each provider implements a simple `get_slug(resource_type: str) -> str` contract and may raise `ValueError` when it cannot resolve the request.

### Default Provider

The default implementation is `adapters.slug.TableSlugProvider`, which queries the `SlugMappings` table. It understands both underscores and spaces in resource type names, so inputs such as `storage_account` and `storage account` resolve to the same slug.

### Custom Providers

You can insert your own providers without modifying route code:

* **Environment override:** Set `SLUG_PROVIDER="my_package.slug:get_providers"`. The attribute can return a single provider or a sequence of providers. Callables are invoked to obtain the provider objects.
* **Programmatic registration:** Call `core.slug_service.set_slug_providers([...])` during startup to replace the chain, or `core.slug_service.register_slug_provider(provider, prepend=True)` to layer one in front of the defaults.

Providers run in order. The first provider that returns a non-empty slug wins; errors are suppressed until all providers fail. This pluggable architecture makes it easy to combine cached lookups, REST calls, or alternate data stores with the built-in table-backed provider.

---

Next: [🚀 Deployment Guide](deployment.md)
