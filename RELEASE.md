# Release process

Maintainers should follow this process to create a new release:

1. Ensure `main` is up to date and tests pass locally.
2. Update `CHANGELOG.md` with notable changes for the new release.
3. Bump the semantic version tag (e.g., `v0.6.0`) and push the tag:

```bash
git tag -a v0.6.0 -m "v0.6.0: short description"
git push origin v0.6.0
```

4. GitHub Actions will create a release and attach artifacts if configured,
   or maintainers can create the release via the GitHub UI.
5. Announce the release as appropriate and update any downstream consumers.
