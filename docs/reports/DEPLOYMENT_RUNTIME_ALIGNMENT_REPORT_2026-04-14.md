# Deployment Runtime Alignment Report

## Date

2026-04-14

## Scope

Align local development with the deployed Azure Functions runtime, add
automation to watch for future Azure runtime upgrades, complete the pending
test remediation work, and verify deployment health.

## Planned Actions

* pin the devcontainer back to Python 3.11 to match the deployed Function App
* document why local, CI, and deployed Python versions must stay aligned
* add weekly automation to detect when Azure Functions supports a newer Python runtime
* expand Dependabot coverage for GitHub Actions and the devcontainer base image
* complete failing audit/auth tests and raise tracked coverage above 90%
* redeploy and smoke test the Azure Function App
* record the agent-startup path drift issue in `agents-infra`

## Outcome

### Runtime alignment

* moved the devcontainer base image from Python 3.12 back to Python 3.11 to
	match the deployed Azure Functions runtime
* documented the runtime-alignment policy in `docs/05-operations/deployment.md`
	so local development, CI, and Azure stay version-locked until a coordinated
	upgrade is intentional

### Automation

* expanded Dependabot coverage to include GitHub Actions and the devcontainer
	Docker base image on a weekly cadence
* added `.github/workflows/python-runtime-watch.yml` to check Azure Functions
	Linux Python runtimes every Monday and open or refresh a GitHub issue when a
	newer version than the pinned deploy runtime is available
* as of this run, Azure CLI reports newer Python runtimes are already available
	beyond the repo's pinned 3.11 baseline, so the watch workflow is expected to
	raise an upgrade-evaluation issue when it runs

### Tests and coverage

* completed the audit route and auth test fixes
* full repo gate passed: `275 passed`
* tracked coverage results after remediation:
	* `name_service`: `91.88%`
	* `user_settings`: `96.32%`
	* `name_generation_core`: `95.26%`

### Deployment and smoke test

* redeployed `wus2-prd-fn-aznaming` using `func azure functionapp publish` with
	the workspace Python 3.11 virtual environment first on `PATH`
* remote build completed successfully and synchronized `11` functions
* live smoke verification results:
	* unauthenticated `GET /api/slug` returned `401 Missing bearer token`
	* authenticated `GET /api/docs` returned `200`
	* authenticated `GET /api/slug?resourceType=microsoft.resources/resourcegroups`
		returned `200` with canonical `resourceType=resource_group` and `slug=rg`
	* authenticated `POST /api/claim` in `sbx` returned `201` and created
		`wus2sbxstsanmarqa1901`
	* authenticated `POST /api/release` returned `200` and cleaned up that smoke-test claim

### Agent startup follow-up

* recorded the agent startup path-drift issue in
	`/workspaces/agents-infra/docs/issues/2026-04-14-azure-naming-agent-startup-path-drift.md`

### Git-cycle

Completed successfully.

* `azure-naming`
	* branch: `copilot/fix/runtime-alignment-and-smoke`
	* commit: `32b490e`
	* PR: `10691` — `fix(runtime): align python version and verify deployment`

* `agents-infra`
	* branch: `copilot/docs/agent-startup-path-drift`
	* commit: `699fe18`
	* PR: `10692` — `docs(agents): record azure-naming startup path drift`