# Terraform Provider ACR Scripts

Utility scripts for building, publishing, and pulling the `sanmar/naming`
Terraform provider to/from Azure Container Registry (ACR) as OCI artifacts.

## Scripts

### `publish_provider_acr.sh`

Builds the Go provider binary from `terraform-provider-sanmar/` and pushes it
to ACR as a versioned OCI artifact.

```bash
# Build and publish (auto-detects version from source)
bash tools/publish_provider_acr.sh

# Publish a specific version
bash tools/publish_provider_acr.sh --version 1.1.0

# Skip build, publish existing binary
bash tools/publish_provider_acr.sh --skip-build
```

**Prerequisites:**
- Active `az login` session with ACR push access
- Go toolchain (downloaded automatically if missing)
- `oras` CLI (downloaded automatically if missing)

**ACR target:** `wus2prdcrsanmariac.azurecr.io/terraform/providers/sanmar/naming`

### `pull_provider_acr.sh`

Pulls the provider binary from ACR and installs it into the local Terraform
filesystem mirror so `terraform init` can resolve `sanmar/naming`.

```bash
# Pull latest version
bash tools/pull_provider_acr.sh

# Pull a specific version
bash tools/pull_provider_acr.sh --version 1.1.0

# Show currently installed version(s)
bash tools/pull_provider_acr.sh --check
```

**Prerequisites:**
- Active `az login` session with ACR pull access
- `oras` CLI (downloaded automatically if missing)

**Install location:** `~/.config/terraform/providers/registry.terraform.io/sanmar/naming/<version>/linux_amd64/`

## Workflow

A typical provider release cycle:

1. Make changes in `terraform-provider-sanmar/`
2. Update the `VERSION` file (or pass `--version`)
3. Run `bash tools/publish_provider_acr.sh` to build and push
4. Run `bash tools/pull_provider_acr.sh` on target machines to install
5. Run `terraform init` in the consuming project — the provider resolves from the filesystem mirror
