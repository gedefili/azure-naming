# AI Contribution Guidelines

This project relies on Azure Function apps backed by the shared `core/` domain package and `adapters/` integration layer. When preparing changes, please observe the following rules so that automated checks and human reviews remain consistent:

## Testing and coverage
- Always run `python tools/run_tests_with_coverage.py` before opening a pull request. This command executes the unit tests and enforces an 80% minimum coverage threshold for the critical components (`core/name_service.py`, `core/user_settings.py`, and the naming rule helpers under `core/`).
- The GitHub Actions workflow (`.github/workflows/tests.yml`) runs the same command on every push and on pull requests that target the `main` branch. The workflow uploads a `coverage-summary.json` artifact with per-component results.
- If you need to mark a file or code path as non-critical for coverage, include an inline `# pragma: no cover` annotation together with a short justification explaining why integration testing is required.

## Code organisation
- The Azure Function entry points under directories such as `claim_name`, `release_name`, and `slug_sync` are intentionally lightweight and delegate to the shared services. New business logic should live under `core/` (domain logic) or `adapters/` (integration points) so that it remains testable.
- Prefer extending the existing unit tests in `tests/` to cover new behaviour. The custom coverage harness is based on Python's `trace` module, so dynamically generated code may require explicit tests to be counted.

## Dependencies
- Runtime dependencies are defined in `requirements.txt`. The CI workflow installs only `pytest` in addition to those dependencies; avoid adding extra test-only libraries unless they are strictly necessary.

Adhering to these guidelines will keep the automated checks passing and maintain the repository's quality bar.
