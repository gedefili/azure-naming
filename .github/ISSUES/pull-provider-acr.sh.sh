#!/usr/bin/env bash
#
# Repository: tools-iac
# Path: bash/naming/pull-provider-acr.sh
# Purpose: Pull the sanmar/naming Terraform provider from ACR and install into the local filesystem mirror
# Author: Infrastructure Team / GitHub Copilot
# Created: 2026-04-13
# Last-Modified: 2026-04-13
# Version: 1.0.0
# Execution-Context: container
# Category: naming
#
# Usage:
#   bash /workspaces/tools-iac/bash/naming/pull-provider-acr.sh
#   bash /workspaces/tools-iac/bash/naming/pull-provider-acr.sh --version 1.0.0
#   bash /workspaces/tools-iac/bash/naming/pull-provider-acr.sh --check
#
# Prerequisites:
#   - az login session with ACR pull access
#   - oras CLI (downloaded automatically if missing)
#
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────

ACR_NAME="wus2prdcrsanmariac"
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
ACR_SUBSCRIPTION="management-iac"
REPOSITORY="terraform/providers/sanmar/naming"

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/home/vscode/.config}"
MIRROR_ROOT="${XDG_CONFIG_HOME}/terraform/providers"
PROVIDER_NAMESPACE="registry.terraform.io/sanmar/naming"

ORAS_VERSION="1.2.2"
VERSION=""

# ─── Helpers ─────────────────────────────────────────────────────────────────

log() { printf "[naming-provider] %s\n" "$*" >&2; }
err() { printf "[naming-provider] ERROR: %s\n" "$*" >&2; exit 1; }

show_usage() {
  cat <<'USAGE'
Usage: pull-provider-acr.sh [OPTIONS]

Options:
  --version VER   Provider version to pull (default: latest)
  --check         Show installed version and exit
  --help          Show this help

Pulls the sanmar/naming Terraform provider from ACR and installs it into
the local filesystem mirror at ~/.config/terraform/providers.
USAGE
}

# ─── Tooling ─────────────────────────────────────────────────────────────────

ensure_oras() {
  if command -v oras >/dev/null 2>&1; then
    ORAS_CMD="oras"
    return
  fi

  if [[ -x /tmp/oras ]]; then
    ORAS_CMD="/tmp/oras"
    return
  fi

  log "Downloading oras ${ORAS_VERSION}..."
  curl -fsSL "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_amd64.tar.gz" -o /tmp/oras.tar.gz
  tar -C /tmp -xzf /tmp/oras.tar.gz oras
  chmod +x /tmp/oras
  rm -f /tmp/oras.tar.gz
  ORAS_CMD="/tmp/oras"
}

# ─── Check installed ────────────────────────────────────────────────────────

show_installed() {
  local installed_dir="${MIRROR_ROOT}/${PROVIDER_NAMESPACE}"

  if [[ ! -d "${installed_dir}" ]]; then
    log "No sanmar/naming provider installed in filesystem mirror"
    log "Mirror root: ${MIRROR_ROOT}"
    return 1
  fi

  log "Installed versions:"
  for ver_dir in "${installed_dir}"/*/; do
    if [[ -d "${ver_dir}" ]]; then
      local ver
      ver="$(basename "$(dirname "${ver_dir}")" 2>/dev/null || basename "${ver_dir}")"
      local binaries
      binaries="$(find "${ver_dir}" -name 'terraform-provider-naming*' -type f 2>/dev/null | wc -l)"
      log "  ${ver} (${binaries} binary/ies)"
    fi
  done
}

# ─── Pull and install ───────────────────────────────────────────────────────

pull_and_install() {
  ensure_oras

  local tag="${VERSION:-latest}"
  local artifact_ref="${ACR_LOGIN_SERVER}/${REPOSITORY}:${tag}"

  # Authenticate
  log "Authenticating to ${ACR_LOGIN_SERVER}..."
  local acr_token
  acr_token="$(az acr login --name "${ACR_NAME}" --subscription "${ACR_SUBSCRIPTION}" --expose-token --query accessToken -o tsv 2>/dev/null)" \
    || err "Failed to get ACR token. Ensure az login is active."

  "${ORAS_CMD}" login "${ACR_LOGIN_SERVER}" \
    --username "00000000-0000-0000-0000-000000000000" \
    --password "${acr_token}" 2>/dev/null \
    || err "oras login failed"

  # Pull to temp directory
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  log "Pulling ${artifact_ref}..."
  "${ORAS_CMD}" pull "${artifact_ref}" --output "${tmp_dir}" \
    || { rm -rf "${tmp_dir}"; err "Failed to pull artifact. Check version exists in ACR."; }

  # Find the binary
  local binary
  binary="$(find "${tmp_dir}" -name 'terraform-provider-naming_v*' -not -name '*.sha256' -type f | head -1)"
  if [[ -z "${binary}" ]]; then
    err "No provider binary found in pulled artifact"
  fi

  # Extract version from binary filename
  local binary_name
  binary_name="$(basename "${binary}")"
  local provider_version="${binary_name#terraform-provider-naming_v}"

  # Verify checksum if present
  local checksum_file="${tmp_dir}/${binary_name}.sha256"
  if [[ -f "${checksum_file}" ]]; then
    log "Verifying checksum..."
    (cd "${tmp_dir}" && sha256sum -c "${binary_name}.sha256") \
      || err "Checksum verification failed"
  fi

  # Install to mirror
  local target_dir="${MIRROR_ROOT}/${PROVIDER_NAMESPACE}/${provider_version}/linux_amd64"
  mkdir -p "${target_dir}"
  cp "${binary}" "${target_dir}/${binary_name}"
  chmod 0755 "${target_dir}/${binary_name}"

  log "Installed: ${PROVIDER_NAMESPACE} v${provider_version}"
  log "  Binary: ${target_dir}/${binary_name}"

  rm -rf "${tmp_dir}"

  log ""
  log "terraform init will now resolve sanmar/naming automatically."
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
  local mode="pull"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version)
        [[ $# -lt 2 ]] && err "--version requires a value"
        VERSION="$2"; shift 2 ;;
      --check)
        mode="check"; shift ;;
      --help|-h)
        show_usage; exit 0 ;;
      *)
        err "Unknown option: $1" ;;
    esac
  done

  if [[ "${mode}" == "check" ]]; then
    show_installed
    return $?
  fi

  pull_and_install
}

main "$@"
