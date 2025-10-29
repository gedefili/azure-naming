```markdown
# 📝 Changelog

All notable changes to the Azure Naming Function project will be documented in this file.

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html): `MAJOR.MINOR.PATCH`


## [1.5.1] - 2025-10-29

### Fixed

* Added missing "Slug Sync" request to `postman-local-collection.json` — this request must be run first to populate the `SlugMappings` table before claiming names
* Enhanced Postman documentation with clear setup order, improved troubleshooting, and error diagnosis guidance

---

## [1.5.0] - 2025-12-19

### Added

* `tools.lib` package with 4 reusable utility modules for cross-project use:
  - `storage_config`: Azurite configuration and endpoint helpers
  - `token_utils`: JWT decoding and timestamp utilities
  - `process_utils`: Subprocess management, port detection, cross-platform process termination
  - `bootstrap_utils`: Centralized logging, watchdog thread utilities, directory helpers
* 20 unit tests for all library modules (100% coverage)
* Public API facade with 28 exports from `tools.lib.__init__`

### Changed

* Refactored 3 tool scripts to use new `tools.lib` modules:
  - `tools/get_access_token.py`: -62% reduction (120 → 46 lines)
  - `tools/run_integration_locally.py`: -51% reduction (140 → 68 lines)
  - `tools/start_local_stack.py`: -42% reduction (382 → 220 lines)
* Eliminated 40 lines of duplication across tool scripts
* Reorganized documentation into 6 logical categories with master index:
  - `docs/01-planning/`: Planning and process documentation
  - `docs/02-getting-started/`: Quick start and authentication guides
  - `docs/03-api-reference/`: API schema and usage documentation
  - `docs/04-development/`: Development guides, architecture, testing tools
  - `docs/05-operations/`: Deployment, security, cost, and release documentation
  - `docs/06-refactoring/`: Refactoring plans and completion records
* Created `docs/index.md` as comprehensive master index with 31 documents indexed
* Created category README files for quick orientation

### Fixed

* Ensured all scripts support execution from any working directory via proper sys.path configuration

---

## [1.3.0] - 2025-10-09

### Added

* JSON discovery endpoints (`/api/rules` and `/api/rules/{resource_type}`) for naming templates and segment mappings.
* Rule introspection helpers (`describe_rule`, `list_resource_types`) to power friendlier API responses and docs.
* Documentation covering test client app registrations, naming rule exploration, and bearer token workflows.

### Changed

* Marked the deployment guide as on hold while rollout is deferred.
* Clarified Entra scope creation, role setup, and `.default` usage in authentication docs.

---

## [1.3.1] - 2025-10-09

### Removed

* Deprecated `utils/` compatibility package now that all imports target the `core/`, `adapters/`, and `providers/` modules directly.

### Changed

* Documentation and contributor guidelines now reference the modern module layout.

### Fixed

* Corrected the `/audit_bulk` route to pass `query_filter` when calling `TableClient.query_entities`, preventing runtime `TypeError` when query parameters are supplied.

---

## [1.2.0] - 2025-10-08

### Added

* Documented the local bootstrap workflow, including processes, ports, and cleanup commands.

### Changed

* Tightened the dev stack script to guard against lingering debug sessions and ensure graceful shutdowns.
* Modernized auth utility type hints to comply with current Python typing checks.

---

## [1.1.0] - 2025-10-08

### Added

* Pluggable naming rule providers with display metadata for responses
* Built-in US strict rule provider enforcing region, environment, and segment requirements
* Documentation covering custom provider usage and updated module layout guidance

### Changed

* Refactored `function_app.py` into modular route packages for readability and maintainability
* API responses now include a `display` block derived from naming rules for consistent presentation

### Added

* Initial Azure Function-based naming service
* Support for:

  * Claiming, releasing, and auditing names
  * Slug mapping sync from GitHub
  * Weekly timer to refresh slugs
  * Full RBAC integration with Entra ID
  * Shared auth and slug validation utilities
  * Markdown documentation: usage, schema, deployment
  * Architecture diagram

---

## [1.0.0] - 2025-07-24

### Added

* Initial Azure Function-based naming service (see 1.1.0 entry for details)

---

## \[0.1.0] - 2025-07-15

### Prototype

* Terraform-based naming helper with manual overrides
* Static slug loading from file
* Conceptual work on audit and RBAC approach

---

## [0.5.0] - 2025-10-15

### Added

* Table-backed slug provider (`adapters/slug.py`) and `TableSlugProvider` used by the slug resolution service.
* JSON-backed naming rule layer (`rules/` + `providers/json_rules.py`) and rule discovery endpoints.
* Unit tests for slug adapter and slug service environment loading (`tests/test_slug_adapter.py`, `tests/test_slug_service_env.py`).

### Changed

* Removed legacy Python-based US rule provider (`providers/us_rules.py`).
* Restored slug adapter and updated core slug service to use the pluggable provider chain.

### Fixed

* Import-time failures caused by a missing slug adapter file.

---

*This changelog will be updated as the project evolves.*

```