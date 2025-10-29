# JSON Naming Rules Directory

This folder contains layerable JSON files that describe naming rules. Each file
represents a **rule layer**. Layers are merged in ascending order by
`metadata.priority`; later (higher priority) layers can override fields from
previous ones.

Files with `metadata.enabled: false` are skipped, allowing you to keep example or
optional overlays in the repository. To activate such a layer, flip `enabled` to
`true`.

## File schema

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `metadata.name` | string | ✓ | Human-friendly name used for logging/debugging. |
| `metadata.priority` | integer | ✓ | Determines precedence. Higher values win. |
| `metadata.enabled` | boolean | ✗ (default `true`) | Skip the file when `false`. |
| `metadata.description` | string | ✗ | Documentation for operators. |
| `default` | object | ✗ (required in at least one layer) | Defines the global fallback naming rule. Should include `segments`, `max_length`, etc. |
| `resources` | object | ✗ | Map of resource types to rule overrides. |

### Rule properties

Each `default` or `resources.<type>` block can define the following properties.
Any missing field inherits from the previously merged rule (either the prior
layer for that resource or the default rule when no resource-specific rule
exists yet).

| Property | Type | Description |
| --- | --- | --- |
| `segments` | array of strings | Ordered segments used to compose the final name. |
| `max_length` | integer | Maximum allowed length of the generated name. |
| `require_sanmar_prefix` | boolean | Adds the `sanmar-` prefix when true. Also makes `{sanmar_prefix}` available in templates. |
| `display` | array | Optional array of display field objects (`key`, `label`, `description`, `optional`). |
| `name_template` | string | Optional template override for assembling names. Available variables: `{slug}`, `{region}`, `{environment}`, `{sanmar_prefix}` (when `require_sanmar_prefix: true`), and any custom segments like `{system_short}`, `{index_segment}`. |
| `summary_template` | string | Optional summary text template rendered for API responses. |
| `validators` | object | Declarative validation rules (see below). |

### Declarative validators

Validators are turned into runtime checks that run before a name is accepted.
They map onto the existing `NamingRule.validators` interface.

* `allowed_values`: mapping of payload keys to the list of accepted string values
  (case-insensitive). Example:
  ```json
  "validators": {
    "allowed_values": {
      "region": ["wus", "wus2"],
      "environment": ["prd", "stg"]
    }
  }
  ```
* `required`: array of keys that must be present and non-empty.
* `require_any`: mapping of logical names to arrays of keys. At least one key in
  each array must be supplied. This is useful for aliases such as `system`
  versus `system_short`.

Validators are additive per layer; specifying the same validator type in a later
layer replaces the earlier definition for that resource.

### Template variable examples

When `name_template` is specified, you can control name assembly using template variables:

```json
{
  "storage_account": {
    "require_sanmar_prefix": true,
    "name_template": "{sanmar_prefix}-{region}-{environment}-{slug}"
  }
}
```

Available template variables:
- `{sanmar_prefix}`: The Sanmar identifier (available when `require_sanmar_prefix: true`)
- `{slug}`: Resource type slug (e.g., "st" for storage_account)
- `{region}`: Azure region (e.g., "wus2")
- `{environment}`: Environment (e.g., "prod")
- `{system_short}`, `{index_segment}`, etc.: Any custom segment from your inputs

Example outputs:
- Template: `"{sanmar_prefix}-{region}-{environment}-{slug}"` → `"sanmar-wus2-prod-st"`
- Template: `"{slug}-{sanmar_prefix}-{region}"` → `"st-sanmar-wus2"` (prefix in middle)
- Template: `"{region}-{environment}-{slug}-{sanmar_prefix}"` → `"wus2-prod-st-sanmar"` (prefix at end)

## Example overlays

* `base.json`: default rule set shipped with the service.
* `us_strict.json`: optional storage-account overlay that reintroduces the
  stricter checks formerly handled in the legacy `USStrictRuleProvider`. Toggle
  `metadata.enabled` to `true` to enforce the constraints.

To add your own overlay, drop another `*.json` file in this directory with a
higher `metadata.priority`. Provide only the fields you need to change; the
loader will inherit the rest from lower-priority layers.
