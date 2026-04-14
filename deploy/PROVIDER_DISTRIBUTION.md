# Terraform Provider Distribution

This document describes the build, publish, and install workflow for the
`sanmar/naming` Terraform provider distributed via Azure Container Registry (ACR).

## Architecture

```
azure-naming repo                        ACR (OCI)                         Consumer repos
┌─────────────────────┐     publish      ┌──────────────────┐    pull      ┌──────────────┐
│ terraform-provider- │ ──────────────►  │ wus2prdcrsanmariac│ ─────────► │ environs-iac │
│ sanmar/             │  tools/publish_  │ .azurecr.io/     │  tools-iac/ │ modules-iac  │
│   provider/*.go     │  provider_acr.sh │ terraform/       │  pull-      │ etc.         │
│   main.go           │                  │ providers/sanmar/│  provider-  │              │
│   go.mod            │                  │ naming           │  acr.sh     │              │
└─────────────────────┘                  └──────────────────┘             └──────────────┘
```

## Script Placement Rationale

| Script | Location | Reason |
|--------|----------|--------|
| `publish_provider_acr.sh` | `azure-naming/tools/` | Builds from Go source in `terraform-provider-sanmar/` which lives in this repo. Tightly coupled to source — must ship with it. |
| `pull-provider-acr.sh` | `tools-iac/bash/naming/` | Consumer-side installation tool. No dependency on provider source code. Used by any repo that needs the provider binary. Cross-repo utilities belong in `tools-iac`. |

### Why not both in `tools-iac`?

The publish script references the provider Go source directory for building.
Placing it in `tools-iac` would create a cross-repo build dependency — the
script would only work when `azure-naming` is also checked out, and
path assumptions would be fragile. Build scripts belong with their source.

### Why not both in `azure-naming`?

The pull script is a consumer tool. Consumers should not need to clone the
`azure-naming` repo just to install the provider binary. `tools-iac` is the
standard location for shared CLI utilities across the platform.

## Usage

### Publishing (from azure-naming)

```bash
# Build and publish with auto-detected version
bash tools/publish_provider_acr.sh

# Publish a specific version
bash tools/publish_provider_acr.sh --version 1.0.0

# Skip build, publish existing binary
bash tools/publish_provider_acr.sh --skip-build
```

### Pulling (from tools-iac)

```bash
# Install latest version
bash /workspaces/tools-iac/bash/naming/pull-provider-acr.sh

# Install specific version
bash /workspaces/tools-iac/bash/naming/pull-provider-acr.sh --version 1.0.0

# Check installed version
bash /workspaces/tools-iac/bash/naming/pull-provider-acr.sh --check
```

### After installing, Terraform resolves the provider automatically

```hcl
terraform {
  required_providers {
    sanmar = {
      source  = "sanmar/naming"
      version = "1.0.0"
    }
  }
}
```

## Prerequisites

- **Publish**: `az login` with ACR push access, Go toolchain (auto-downloaded)
- **Pull**: `az login` with ACR pull access
- Both scripts auto-download `oras` CLI if not present

## Authentication Flow

The provider authenticates to the Azure Naming Function App using
`DefaultAzureCredential` (Bearer JWT), not function keys. This requires
the Function App to use `AuthLevel.ANONYMOUS` at the runtime level, with
application-layer JWT validation via `require_role()`. See the auth fix
in `app/__init__.py`.
