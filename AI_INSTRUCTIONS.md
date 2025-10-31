# AI Contribution Guidelines```markdown

# AI Contribution Guidelines

This project relies on Azure Function apps backed by the shared `core/` domain package and `adapters/` integration layer. When preparing changes, please observe the following rules so that automated checks and human reviews remain consistent:

This project relies on Azure Function apps backed by the shared `core/` domain package and `adapters/` integration layer. When preparing changes, please observe the following rules so that automated checks and human reviews remain consistent:

## Testing and coverage

- Always run `python tools/run_tests_with_coverage.py` before opening a pull request. This command executes the unit tests and enforces an 80% minimum coverage threshold for the critical components (`core/name_service.py`, `core/user_settings.py`, and the naming rule helpers under `core/`).## Testing and coverage

- The GitHub Actions workflow (`.github/workflows/tests.yml`) runs the same command on every push and on pull requests that target the `main` branch. The workflow uploads a `coverage-summary.json` artifact with per-component results.- Always run `python tools/run_tests_with_coverage.py` before opening a pull request. This command executes the unit tests and enforces an 80% minimum coverage threshold for the critical components (`core/name_service.py`, `core/user_settings.py`, and the naming rule helpers under `core/`).

- If you need to mark a file or code path as non-critical for coverage, include an inline `# pragma: no cover` annotation together with a short justification explaining why integration testing is required.- The GitHub Actions workflow (`.github/workflows/tests.yml`) runs the same command on every push and on pull requests that target the `main` branch. The workflow uploads a `coverage-summary.json` artifact with per-component results.

- If you need to mark a file or code path as non-critical for coverage, include an inline `# pragma: no cover` annotation together with a short justification explaining why integration testing is required.

## Code organisation

- The Azure Function entry points under directories such as `claim_name`, `release_name`, and `slug_sync` are intentionally lightweight and delegate to the shared services. New business logic should live under `core/` (domain logic) or `adapters/` (integration points) so that it remains testable.## Code organisation

- Prefer extending the existing unit tests in `tests/` to cover new behaviour. The custom coverage harness is based on Python's `trace` module, so dynamically generated code may require explicit tests to be counted.- The Azure Function entry points under directories such as `claim_name`, `release_name`, and `slug_sync` are intentionally lightweight and delegate to the shared services. New business logic should live under `core/` (domain logic) or `adapters/` (integration points) so that it remains testable.

- Prefer extending the existing unit tests in `tests/` to cover new behaviour. The custom coverage harness is based on Python's `trace` module, so dynamically generated code may require explicit tests to be counted.

## Dependencies

- Runtime dependencies are defined in `requirements.txt`. The CI workflow installs only `pytest` in addition to those dependencies; avoid adding extra test-only libraries unless they are strictly necessary.## Dependencies

- Runtime dependencies are defined in `requirements.txt`. The CI workflow installs only `pytest` in addition to those dependencies; avoid adding extra test-only libraries unless they are strictly necessary.

Adhering to these guidelines will keep the automated checks passing and maintain the repository's quality bar.

Adhering to these guidelines will keep the automated checks passing and maintain the repository's quality bar.

## Documentation organisation

## Release and CI guidance

All markdown documentation must be stored in the `docs/` directory, properly organized by topic. The root directory should only contain:

- `README.md` - Project overview and getting startedThis repository uses GitHub Actions to run tests on pushes and pull requests. Releases are created from annotated tags and will automatically bundle artifacts via the `release` workflow.

- `LICENSE` - License file

- `AI_INSTRUCTIONS.md` - This fileWhen preparing a release:



### Documentation folder structure:- Update `CHANGELOG.md` with the release notes.

- `docs/01-planning/` - Planning, architecture, and design decisions- Create an annotated tag (e.g., `v0.6.0`) and push it to `origin`.

- `docs/02-getting-started/` - Setup, authentication, and quick start guides- The `release` workflow will pick up the tag and attach artifacts to the release.

- `docs/03-api-reference/` - API documentation and schemas

- `docs/04-development/` - Development guides, module structure, and local testing## AI-assisted edits policy

- `docs/05-operations/` - Operations, troubleshooting, and quick references

- `docs/06-security/` - Security documentation, audits, and vulnerability trackingIf an AI assistant modifies files:

- `docs/index.md` - Documentation index and navigation

- Keep changes small and focused. Make one logical change per commit/PR.

### When creating new documentation:- Always run the test suite and update coverage artifacts before opening a PR.

1. Determine the appropriate folder based on content type- Leave a brief human-written summary in the PR describing why the AI made the changes and any follow-up for maintainers.

2. Create the file with a descriptive name (e.g., `SECURITY_ANALYSIS.md` becomes `docs/06-security/analysis.md`)

3. Add an entry to the relevant folder's `README.md` or the main `docs/index.md````

4. Never commit `.md` files to the root directory unless required by git/GitHub conventions# AI Contribution Guidelines



## Release and CI guidanceThis project relies on Azure Function apps backed by the shared `core/` domain package and `adapters/` integration layer. When preparing changes, please observe the following rules so that automated checks and human reviews remain consistent:



This repository uses GitHub Actions to run tests on pushes and pull requests. Releases are created from annotated tags and will automatically bundle artifacts via the `release` workflow.## Testing and coverage

- Always run `python tools/run_tests_with_coverage.py` before opening a pull request. This command executes the unit tests and enforces an 80% minimum coverage threshold for the critical components (`core/name_service.py`, `core/user_settings.py`, and the naming rule helpers under `core/`).

When preparing a release:- The GitHub Actions workflow (`.github/workflows/tests.yml`) runs the same command on every push and on pull requests that target the `main` branch. The workflow uploads a `coverage-summary.json` artifact with per-component results.

- If you need to mark a file or code path as non-critical for coverage, include an inline `# pragma: no cover` annotation together with a short justification explaining why integration testing is required.

- Update `docs/01-planning/CHANGELOG.md` with the release notes.

- Create an annotated tag (e.g., `v0.6.0`) and push it to `origin`.## Code organisation

- The `release` workflow will pick up the tag and attach artifacts to the release.- The Azure Function entry points under directories such as `claim_name`, `release_name`, and `slug_sync` are intentionally lightweight and delegate to the shared services. New business logic should live under `core/` (domain logic) or `adapters/` (integration points) so that it remains testable.

- Prefer extending the existing unit tests in `tests/` to cover new behaviour. The custom coverage harness is based on Python's `trace` module, so dynamically generated code may require explicit tests to be counted.

## AI-assisted edits policy

## Dependencies

If an AI assistant modifies files:- Runtime dependencies are defined in `requirements.txt`. The CI workflow installs only `pytest` in addition to those dependencies; avoid adding extra test-only libraries unless they are strictly necessary.



- Keep changes small and focused. Make one logical change per commit/PR.Adhering to these guidelines will keep the automated checks passing and maintain the repository's quality bar.

- Always run the test suite and update coverage artifacts before opening a PR.
- Leave a brief human-written summary in the PR describing why the AI made the changes and any follow-up for maintainers.
- After completing work, organize documentation by moving `.md` files to appropriate `docs/` subfolders.
