# AI Contribution Guidelines

This project relies on Azure Functions backed by the shared `core/` domain
package and `adapters/` integration layer. Follow these rules so automated
checks and human reviews stay consistent.

## Testing and coverage

- Always run `python tools/run_tests_with_coverage.py` before opening a pull request.
- The Azure DevOps `azure-naming` pipeline runs the same command for PRs, `main`, and tag builds and publishes `coverage-summary.json` as an artifact.
- If you need to mark a file or code path as non-critical for coverage, include `# pragma: no cover` with a short justification.

## Code organisation

- Keep Azure Function entry points lightweight. Business logic belongs in `core/` or `adapters/`.
- Prefer extending the existing tests in `tests/` for new behaviour.

## Dependencies

- Runtime dependencies live in `requirements.txt`.
- Avoid adding test-only dependencies unless they are strictly necessary.

## Documentation organisation

All markdown documentation must live under `docs/`, properly organized by topic.
The repository root should only contain top-level project files such as:

- `README.md`
- `LICENSE`
- `AI_INSTRUCTIONS.md`

When creating new documentation:

1. Choose the correct `docs/` subfolder for the content.
2. Use a descriptive file name.
3. Add the new document to the relevant `README.md` or `docs/index.md`.
4. Do not add new root-level markdown files unless required by platform conventions.

## Release and CI guidance

- Azure DevOps is the system of record for CI, deployment, and release automation.
- Pipeline definitions live in `azure-pipelines.yml`.
- When preparing a release, update `docs/01-planning/CHANGELOG.md`, create an annotated tag, and push it to `origin` so the Azure DevOps release stage can publish the release artifact.

## AI-assisted edits policy

- Keep changes small and focused.
- Make one logical change per commit or PR when possible.
- Always run the test suite and update coverage artifacts before opening a PR.
- Leave a brief human-written summary in the PR describing why the AI made the changes and any follow-up for maintainers.
