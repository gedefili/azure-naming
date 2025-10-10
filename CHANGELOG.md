# 📝 Changelog

All notable changes to the Azure Naming Function project will be documented in this file.

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html): `MAJOR.MINOR.PATCH`


## [1.3.0] - 2025-10-09

### Added

* JSON discovery endpoints (`/api/rules` and `/api/rules/{resource_type}`) for naming templates and segment mappings.
* Rule introspection helpers (`describe_rule`, `list_resource_types`) to power friendlier API responses and docs.
* Documentation covering test client app registrations, naming rule exploration, and bearer token workflows.

### Changed

* Marked the deployment guide as on hold while rollout is deferred.
* Clarified Entra scope creation, role setup, and `.default` usage in authentication docs.

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

*This changelog will be updated as the project evolves.*
