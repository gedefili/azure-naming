#!/usr/bin/env bash
# =============================================================================
# Repository: azure-naming
# Path: tools/local_naming_stack.sh
# Purpose: One-stop local dev harness for the Naming Experience. Builds the SPA
#          and serves it via `vite preview`, optionally starting the Function
#          host (azurite + func start) so the SPA can hit a real backend.
# Author: SanMar Platform Team
# Created: 2026-04-27
# Last-Modified: 2026-04-27
# Version: 1.0.0
#
# Usage:
#   bash tools/local_naming_stack.sh up            # spa + backend
#   bash tools/local_naming_stack.sh up --spa-only # spa preview only
#   bash tools/local_naming_stack.sh screenshots   # spa preview + playwright
#   bash tools/local_naming_stack.sh down          # stop everything
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT/web"
PREVIEW_PORT="${PREVIEW_PORT:-4173}"
FUNC_PORT="${FUNC_PORT:-7071}"
PID_DIR="$ROOT/.local-stack"
mkdir -p "$PID_DIR"

log()  { printf '\033[1;36m[stack]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[stack]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[stack]\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

stop_pidfile() {
  local f="$1"
  [ -f "$f" ] || return 0
  local pid
  pid="$(cat "$f" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null || true
  rm -f "$f"
}

cmd_down() {
  log "stopping local naming stack"
  stop_pidfile "$PID_DIR/preview.pid"
  stop_pidfile "$PID_DIR/func.pid"
  pkill -f "vite preview --port $PREVIEW_PORT" 2>/dev/null || true
}

start_preview() {
  require_cmd npm
  cd "$WEB_DIR"
  if [ ! -d node_modules ]; then
    log "installing web/ dependencies"
    npm install --legacy-peer-deps --no-audit --no-fund
  fi
  if [ ! -d dist ]; then
    log "building SPA"
    npm run build
  fi
  log "starting vite preview on http://127.0.0.1:$PREVIEW_PORT"
  nohup npm run preview -- --port "$PREVIEW_PORT" --host 127.0.0.1 \
    >"$PID_DIR/preview.log" 2>&1 &
  echo $! >"$PID_DIR/preview.pid"

  for _ in $(seq 1 30); do
    if curl -fsS --max-time 2 "http://127.0.0.1:$PREVIEW_PORT/" >/dev/null 2>&1; then
      log "preview ready"
      return 0
    fi
    sleep 1
  done
  die "preview did not become ready within 30s; see $PID_DIR/preview.log"
}

start_backend() {
  if ! command -v func >/dev/null 2>&1; then
    warn "azure-functions-core-tools (func) not installed; skipping backend"
    return 0
  fi
  log "starting Function host (port $FUNC_PORT)"
  cd "$ROOT"
  nohup func start --port "$FUNC_PORT" >"$PID_DIR/func.log" 2>&1 &
  echo $! >"$PID_DIR/func.pid"
}

cmd_up() {
  local spa_only="false"
  for arg in "$@"; do
    [ "$arg" = "--spa-only" ] && spa_only="true"
  done
  start_preview
  [ "$spa_only" = "false" ] && start_backend
  log "stack is up. PIDs in $PID_DIR/"
  log "  spa preview: http://127.0.0.1:$PREVIEW_PORT/"
}

cmd_screenshots() {
  start_preview
  cd "$WEB_DIR"
  if [ ! -d node_modules/@playwright ]; then
    log "installing Playwright browsers"
    npx playwright install --with-deps chromium
  fi
  log "running screenshot suite"
  npm run screenshots
  log "screenshots written to $WEB_DIR/screenshots"
}

case "${1:-up}" in
  up)           shift || true; cmd_up "$@" ;;
  down)         cmd_down ;;
  screenshots)  cmd_screenshots ;;
  *)            die "unknown subcommand: $1 (expected up|down|screenshots)" ;;
esac
