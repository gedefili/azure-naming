#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/azure-naming

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

node --version
npm --version
az version
func --version
azurite --version
go version
oras version
gh --version
jq --version