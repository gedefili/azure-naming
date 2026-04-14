# Release process

Maintainers should follow this process to create a new release:

1. Ensure `main` is up to date and tests pass locally.
2. Update `CHANGELOG.md` with notable changes for the new release.
3. Bump the semantic version tag (e.g., `v0.6.0`) and push the tag:

```bash
git tag -a v0.6.0 -m "v0.6.0: short description"
git push origin v0.6.0
```

4. Azure DevOps will run the `azure-naming` pipeline for the tag and publish a `release` build artifact containing the source tarball.
5. Announce the release as appropriate and update any downstream consumers.

Manual queue example for a tag if needed:

```bash
az pipelines run \
    --organization https://dev.azure.com/sanmarcloud \
    --project "Infrastructure Administration" \
    --name azure-naming \
    --branch refs/tags/v0.6.0
```
