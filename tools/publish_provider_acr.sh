#!/usr/bin/env bash
#
# Repository: azure-naming
# Path: tools/publish_provider_acr.sh
# Purpose: Build and publish the sanmar/naming Terraform provider to ACR as an OCI artifact
# Author: SanMar Platform Team
# Created: 2026-04-13
# Last-Modified: 2026-04-14
# Version: 1.1.0
# Execution-Context: container
# Category: naming
#
# Usage:
#   bash tools/publish_provider_acr.sh
#   bash tools/publish_provider_acr.sh --version 1.0.0
#   bash tools/publish_provider_acr.sh --skip-build
#
# Prerequisites:
#   - az login session with ACR push access
#   - Go toolchain (downloaded automatically if missing)
#   - oras CLI (downloaded automatically if missing)
#
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────

ACR_NAME="wus2prdcrsanmariac"
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
ACR_SUBSCRIPTION="management-iac"
REPOSITORY="terraform/providers/sanmar/naming"

# Resolve provider source relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROVIDER_SOURCE="${REPO_ROOT}/terraform-provider-sanmar"

GO_MIN_VERSION="1.22"
GO_DOWNLOAD_VERSION="1.22.12"
ORAS_VERSION="1.2.2"

# ─── Defaults ────────────────────────────────────────────────────────────────

VERSION=""
SKIP_BUILD=false

# ─── Helpers ─────────────────────────────────────────────────────────────────

log() { printf "[naming-provider] %s\n" "$*" >&2; }
err() { printf "[naming-provider] ERROR: %s\n" "$*" >&2; exit 1; }

show_usage() {
  cat <<'USAGE'
Usage: publish_provider_acr.sh [OPTIONS]

Options:
  --version VER   Provider version to publish (default: read from source)
  --skip-build    Skip Go build, use existing binary
  --help          Show this help

Publishes the sanmar/naming Terraform provider binary to ACR as an OCI artifact.
USAGE
}

# ─── Ensure tooling ──────────────────────────────────────────────────────────

ensure_go() {
  if command -v go >/dev/null 2>&1; then
    log "Using system Go: $(go version)"
    GO_CMD="go"
    return
  fi

  if [[ -x /tmp/go/bin/go ]]; then
    log "Using cached Go at /tmp/go/bin/go"
    GO_CMD="/tmp/go/bin/go"
    return
  fi

  log "Downloading Go ${GO_DOWNLOAD_VERSION}..."
  curl -fsSL "https://go.dev/dl/go${GO_DOWNLOAD_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tar.gz
  rm -rf /tmp/go
  tar -C /tmp -xzf /tmp/go.tar.gz
  rm -f /tmp/go.tar.gz
  GO_CMD="/tmp/go/bin/go"
  log "Go ${GO_DOWNLOAD_VERSION} installed to /tmp/go"
}

ensure_oras() {
  if command -v oras >/dev/null 2>&1; then
    log "Using system oras: $(oras version | head -1)"
    ORAS_CMD="oras"
    return
  fi

  if [[ -x /tmp/oras ]]; then
    log "Using cached oras at /tmp/oras"
    ORAS_CMD="/tmp/oras"
    return
  fi

  log "Downloading oras ${ORAS_VERSION}..."
  curl -fsSL "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_amd64.tar.gz" -o /tmp/oras.tar.gz
  tar -C /tmp -xzf /tmp/oras.tar.gz oras
  chmod +x /tmp/oras
  rm -f /tmp/oras.tar.gz
  ORAS_CMD="/tmp/oras"
  log "oras ${ORAS_VERSION} installed to /tmp/oras"
}

# ─── Build ───────────────────────────────────────────────────────────────────

detect_version() {
  if [[ -n "${VERSION}" ]]; then
    return
  fi

  # Try VERSION file in provider source
  if [[ -f "${PROVIDER_SOURCE}/VERSION" ]]; then
    VERSION="$(cat "${PROVIDER_SOURCE}/VERSION" | tr -d '[:space:]')"
    log "Version from VERSION file: ${VERSION}"
    return
  fi

  # Try go.mod module + git tag
  VERSION="1.0.0"
  log "No VERSION file found; defaulting to ${VERSION}"
}

build_provider() {
  if [[ "${SKIP_BUILD}" == "true" ]]; then
    log "Skipping build (--skip-build)"
    return
  fi

  if [[ ! -d "${PROVIDER_SOURCE}" ]]; then
    err "Provider source not found at ${PROVIDER_SOURCE}"
  fi

  ensure_go

  local binary_name="terraform-provider-naming_v${VERSION}"
  local output_path="${PROVIDER_SOURCE}/${binary_name}"

  log "Building provider v${VERSION}..."
  (
    cd "${PROVIDER_SOURCE}"
    GOPATH=/tmp/gopath CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
      "${GO_CMD}" build \
        -ldflags "-s -w -X main.version=${VERSION}" \
        -o "${binary_name}" .
  )

  if [[ ! -f "${output_path}" ]]; then
    err "Build produced no output at ${output_path}"
  fi

  log "Built: ${output_path} ($(du -h "${output_path}" | cut -f1))"
}

# ─── Publish ─────────────────────────────────────────────────────────────────

publish_to_acr() {
  ensure_oras

  local binary_name="terraform-provider-naming_v${VERSION}"
  local binary_path="${PROVIDER_SOURCE}/${binary_name}"

  if [[ ! -f "${binary_path}" ]]; then
    err "Binary not found at ${binary_path}. Run without --skip-build first."
  fi

  # Authenticate to ACR via Azure CLI
  log "Authenticating to ${ACR_LOGIN_SERVER}..."
  local acr_token
  acr_token="$(az acr login --name "${ACR_NAME}" --subscription "${ACR_SUBSCRIPTION}" --expose-token --query accessToken -o tsv 2>/dev/null)" \
    || err "Failed to get ACR token. Ensure az login is active and you have ACR push access."

  "${ORAS_CMD}" login "${ACR_LOGIN_SERVER}" \
    --username "00000000-0000-0000-0000-000000000000" \
    --password "${acr_token}" 2>/dev/null \
    || err "oras login failed"

  # Create checksum
  local checksum_file="${PROVIDER_SOURCE}/${binary_name}.sha256"
  (cd "${PROVIDER_SOURCE}" && sha256sum "${binary_name}" > "${binary_name}.sha256")

  # Push as OCI artifact with version tag + latest
  local artifact_ref="${ACR_LOGIN_SERVER}/${REPOSITORY}"

  log "Pushing to ${artifact_ref}:${VERSION}..."
  (
    cd "${PROVIDER_SOURCE}"
    "${ORAS_CMD}" push "${artifact_ref}:${VERSION}" \
      --artifact-type "application/vnd.hashicorp.terraform.provider" \
      "${binary_name}:application/octet-stream" \
      "${binary_name}.sha256:text/plain"
  )

  log "Tagging as latest..."
  "${ORAS_CMD}" tag "${artifact_ref}:${VERSION}" "latest"

  # Cleanup checksum
  rm -f "${checksum_file}"

  log ""
  log "Published successfully:"
  log "  ${artifact_ref}:${VERSION}"
  log "  ${artifact_ref}:latest"
  log ""
  log "To pull: oras pull ${artifact_ref}:${VERSION}"
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version)
        [[ $# -lt 2 ]] && err "--version requires a value"
        VERSION="$2"; shift 2 ;;
      --skip-build)
        SKIP_BUILD=true; shift ;;
      --help|-h)
        show_usage; exit 0 ;;
      *)
        err "Unknown option: $1" ;;
    esac
  done

  detect_version
  build_provider
  publish_to_acr

  log "Done. Provider v${VERSION} is available in ACR."
}

main "$@"
