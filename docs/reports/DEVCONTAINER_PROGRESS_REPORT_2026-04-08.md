# Dev Container Progress Report

**Date:** 2026-04-08  
**Scope:** Local development environment hardening, multi-root workspace support, host configuration passthrough, and Azure CLI readiness for local Azure Functions development  
**Author:** GitHub Copilot

---

## Executive Summary

The repository now has a working VS Code dev container configuration for local development using the existing `azure-naming` and `agents-infra` multi-root workspace. The environment was extended to include Azure Functions Core Tools, Azurite, and Azure CLI, and it was updated to work cleanly in a Podman-backed container runtime setup.

This work also removed the dependency on the VS Code-only `func` task provider by aligning the workspace tasks and debug configuration with the repository's existing `tools/start_local_stack.py` bootstrap flow.

The current outcome is a validated development container image that provides:

- Python runtime with project virtual environment bootstrap
- Azure Functions Core Tools (`func`)
- Azurite (`azurite`)
- Azure CLI (`az`)
- Multi-root workspace mounting for both `azure-naming` and `agents-infra`
- Mounted host developer configuration for SSH, Git, GitHub CLI, and Azure CLI state

---

## Objectives Addressed

### 1. Remove dependency on missing VS Code task provider

The workspace previously contained a task with `"type": "func"`, which failed with:

```text
Error: there is no registered task type 'func'.
```

This was resolved by converting the task to a standard shell-based task that runs the repository bootstrap script directly.

### 2. Create a reproducible dev container

A new `.devcontainer/` configuration was added so local development no longer depends on host-level installation of all required tools.

### 3. Support Podman-based development

The local startup flow was updated so Azurite container fallback prefers Podman before Docker, which matches the current workstation setup.

### 4. Support multi-root workspace use inside the container

The container now mounts the parent `/workspaces` directory and uses `/workspaces/azure-naming` as the working folder so the sibling `agents-infra` repository is also accessible.

### 5. Reuse host developer identity and auth state

The container now mounts host configuration paths for:

- `~/.ssh`
- `~/.gitconfig`
- `~/.config/gh`
- `~/.azure`

This allows containerized development to reuse existing SSH keys, Git identity, GitHub CLI authentication, and Azure CLI login state.

### 6. Improve local Azure development tooling

Azure CLI was added to the container image so login, token acquisition, subscription inspection, and local Azure-oriented development workflows can be performed from inside the development environment.

---

## Files Added

### New dev container files

- `.devcontainer/devcontainer.json`
- `.devcontainer/Dockerfile`
- `.devcontainer/postCreate.sh`

### Workspace support file

- `azure-naming.code-workspace`

---

## Files Updated

### Local development and debugging

- `.vscode/tasks.json`
- `.vscode/launch.json`
- `tools/start_local_stack.py`

### Documentation

- `README.md`
- `docs/04-development/local-testing.md`

---

## Implemented Changes

### A. VS Code task and debug flow alignment

The workspace now uses the repository-owned bootstrap path consistently.

Implemented changes:

- Replaced the unsupported `func` task type with a shell task
- Pointed the legacy attach configuration to the same bootstrap flow as the primary debug configuration
- Standardized the debug attach port to `5678`
- Added matching pre-launch and post-debug task behavior

Result:

- The editor no longer depends on the Azure Functions task provider just to start local development

### B. Dev container creation

The new dev container provides a reproducible local environment with the required tools installed at image build time.

Installed toolchain:

- Python 3.12 base image
- Node.js and npm
- Azure Functions Core Tools v4
- Azurite
- Azure CLI

Post-create behavior:

- Creates `.venv` when missing
- Activates the virtual environment
- Upgrades `pip`
- Installs `requirements.txt`
- Verifies `az`, `func`, and `azurite`

### C. Multi-root workspace mount support

The original container setup only mounted the active repository folder. That prevented proper use of the sibling `agents-infra` repo from inside the container.

Implemented changes:

- Mounted `${localWorkspaceFolder}/..` to `/workspaces`
- Set container workspace folder to `/workspaces/azure-naming`
- Updated `azure-naming.code-workspace` to use relative sibling paths instead of host-specific absolute paths

Result:

- Both repositories are available inside the container under the same path structure used outside the container

### D. Host settings passthrough

The dev container now mounts important host developer state.

Mounted paths:

- `${localEnv:HOME}/.ssh` → `/home/vscode/.ssh` (readonly)
- `${localEnv:HOME}/.gitconfig` → `/home/vscode/.gitconfig` (readonly)
- `${localEnv:HOME}/.config/gh` → `/home/vscode/.config/gh`
- `${localEnv:HOME}/.azure` → `/home/vscode/.azure`

Result:

- SSH-based git operations, Git identity, GitHub CLI auth, and Azure CLI auth can be reused from the host

### E. Podman-aware Azurite fallback

The local stack bootstrap script was updated to prefer:

1. `azurite` CLI
2. `podman`
3. `docker`

Result:

- The local stack is compatible with the current Podman-backed environment instead of assuming Docker-first behavior

---

## Validation Performed

### Editor and config validation

Validated successfully:

- `.devcontainer/devcontainer.json`
- `.devcontainer/Dockerfile`
- `.devcontainer/postCreate.sh`
- `azure-naming.code-workspace`
- `.vscode/tasks.json`
- `.vscode/launch.json`
- `tools/start_local_stack.py`

### Image build validation

The dev container image was built successfully through the workstation's `docker` CLI, which is backed by Podman in this environment.

Validated runtime tool availability inside the built image:

- `az 2.85.0`
- `func 4.9.0`
- `azurite 3.35.0`

### Syntax and runtime checks completed

- JSON validation with `jq`
- Shell syntax validation with `bash -n`
- Python syntax validation with byte-compilation / editor diagnostics
- Container image build and runtime execution validation

---

## Issues Encountered and Resolved

### 1. Missing task provider for `func`

**Problem:** VS Code reported that no registered task type `func` existed.  
**Resolution:** Replaced the provider-specific task with a shell task invoking `tools/start_local_stack.py`.

### 2. Missing host tools for local startup

**Problem:** Local startup initially failed because `func` and `azurite` were not available on host `PATH`.  
**Resolution:** Shifted the preferred development path to the dev container where the required tools are baked into the image.

### 3. Inherited broken Yarn apt source in base image

**Problem:** The selected devcontainers Python base image included `/etc/apt/sources.list.d/yarn.list` without a usable signing key in this environment, causing `apt-get update` to fail during image build.  
**Resolution:** Removed the inherited Yarn source before `apt-get update` in the Dockerfile.

### 4. Multi-root workspace path incompatibility inside container

**Problem:** The workspace file referenced `agents-infra` using an absolute host path that would not resolve correctly inside the container.  
**Resolution:** Converted those paths to relative sibling paths and mounted the parent workspace directory.

---

## Current Outcomes

### Completed outcomes

- Dev container scaffolding is in place and validated
- Multi-root workspace use inside the container is supported
- Host SSH, Git, GitHub CLI, and Azure CLI state is available inside the container
- Azure CLI is installed and ready for Azure-oriented workflows
- Local debug/task flow now matches repository-owned scripts instead of editor-specific task providers
- Podman is supported as the preferred fallback container runtime for Azurite

### Practical result today

After a rebuild and reopen in container, a developer should be able to:

- work in both `azure-naming` and `agents-infra`
- run the existing local stack bootstrap from inside the container
- use Azure CLI with mounted host login state
- use Git and SSH operations with existing host identity/configuration

---

## Known Caveats

### 1. Node version warning during npm install

The image currently installs Debian-packaged Node.js `18.x`. During installation of Azure Functions Core Tools dependencies, npm emits `EBADENGINE` warnings because some Azure-related transitive packages now declare `node >= 20`.

**Current status:**

- Build succeeds
- Installed tools run successfully
- No immediate blocker for current development usage

**Recommended follow-up:**

- Move the image to a Node 20+ runtime or install a newer Node version explicitly for longer-term stability

### 2. SSH mount security tradeoff

Mounting `~/.ssh` directly is convenient but broader than SSH agent forwarding.

**Recommendation:**

- Consider replacing full key mounting with SSH agent forwarding plus selective `config` and `known_hosts` mounts if tighter isolation is desired later

---

## Recommended Next Actions

### Immediate

1. Rebuild and reopen the repository in the dev container
2. Verify the multi-root workspace opens with both `azure-naming` and `agents-infra`
3. Run the `Attach to Local Azure Functions` debug configuration from inside the container

### Near-term hardening

1. Upgrade the container Node runtime to 20+
2. Decide whether to keep full `.ssh` mounting or replace it with agent forwarding
3. Add any additional local Azure development tooling only if it materially improves the local Functions workflow

---

## Conclusion

The repository has moved from an incomplete local setup that depended on missing host tooling and editor-specific task providers to a validated, containerized development workflow. The current dev container is suitable for ongoing local Azure Functions development and removes much of the host-specific setup friction without changing the production deployment model.