# 📝 Changelog

All notable changes to the Azure Naming Function project will be documented in this file.

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html): `MAJOR.MINOR.PATCH`


## [1.8.5] - 2026-04-16

### Added

* Added `POST /api/claims/remediate`, an admin-only endpoint that can mark a claim orphaned and reusable or purge it entirely when operator cleanup is required.
* Extended the claim lifecycle record with `ClaimState`, `StateVersion`, and state change timestamps/users so audits can show how a name changed over time.

### Fixed

* Added canonical CAF slug overrides for `container_app`, `container_app_environment`, and `subnet`, so those resource types now resolve to `ca`, `cae`, and `snet` during slug sync.
* Aligned the HTTP slug sync route with the canonical storage schema (`ResourceType`, `FullName`, `Source`, `UpdatedAt`) used by runtime slug lookup.
* Fixed name reuse after release or orphan remediation by updating the existing row instead of failing on a duplicate create for a recyclable name.


## [1.8.4] - 2026-04-16

### Changed

* Added an Azure DevOps `publish_provider` stage that publishes the `sanmar/naming` Terraform provider from `provider-v*` tags.
* Documented the dedicated provider release flow so provider publishing no longer depends on manual local pushes to ACR.

### Fixed

* The Terraform provider now accepts `201 Created` on successful claims and `204 No Content` on successful releases.
* The provider no longer reports a Terraform null object when a slug mapping is missing; it now returns an explicit diagnostic error.
* Added local slug overrides for eight Azure resource types that were absent from the upstream slug source.
* Fixed the provider HTTP retry path so `429 Too Many Requests` responses are retried instead of returned immediately.

## [1.8.3] - 2026-04-14

### Changed

* Replaced the repository's active GitHub Actions workflows with an Azure DevOps multi-stage pipeline in `azure-pipelines.yml`.
* Moved deployment, devcontainer publish, release artifact generation, and manual Postman execution guidance to Azure DevOps.

### Fixed

* Removed the split-brain CI/CD setup where GitHub remained capable of deploying code even though Azure DevOps is now the system of record.

## [1.8.2] - 2026-04-14

### Changed

* The deployment workflow now triggers `POST /api/slug_sync` after every successful Function App publish.
* Deployment documentation now requires the deploy principal to hold the Azure Naming `admin` app role so the post-deploy slug import can authenticate.

### Fixed

* Eliminated the deployment gap where a fresh publish could leave slug mappings stale until a manual sync or the weekly timer ran.

## [1.8.1] - 2026-04-14

### Fixed

* **Deployment pipeline**: Replaced broken pre-built zip deployment with server-side remote build (`scm-do-build-during-deployment: true`). The previous workflow used `pip install --target --platform manylinux2014_x86_64 --only-binary=:all:` to cross-compile dependencies locally, which produced incomplete packages and Python ABI mismatches against the Function App's Python 3.11 runtime. This caused zero functions to register and all routes to return 404.
* **`.funcignore`**: Expanded exclusions to keep test files, docs, Terraform provider source, and tools out of the deployment package while ensuring `adapters/`, `providers/`, `core/`, `app/`, and `rules/` are always included.
* **`WEBSITE_RUN_FROM_PACKAGE` removal**: Deploy workflow now explicitly removes this app setting before deployment, preventing stale zip artifacts from shadowing the live wwwroot.

### Added

* Post-deployment verification job in CI (`verify`) that checks function registration count and smoke-tests `/api/docs`.
* `tools/verify_deployment.py` script for manual post-deploy verification of app settings, registered functions, and endpoint health.

### Changed

* Split `deploy.yml` into three jobs (`test` → `deploy` → `verify`) for clearer failure isolation.
* Deploy job now configures `SCM_DO_BUILD_DURING_DEPLOYMENT=true` and `ENABLE_ORYX_BUILD=true` app settings before push.

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

*This changelog will be updated as the project evolves.*
