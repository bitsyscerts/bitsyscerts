#!/usr/bin/env bash
# server-deploy.sh — one-shot runtime deploy for a bare Ubuntu + Docker server.
#
# This script does NOT require the BitsyCerts source repository to be present.
# Place it in the same directory as docker-compose.yml and .env, then run it.
#
# Usage:
#   ./server-deploy.sh [--skip-migrate] [--skip-sync-logs]
#
#   --skip-migrate    Skip the compose-native `migrate` bootstrap step.
#   --skip-sync-logs  Skip `ctpool sync-logs`       (skips the CT log list
#                     refresh; useful if the list was already synced recently).
#
# Requirements:
#   - Docker Engine 25+ with the Compose plugin (docker compose v2)
#   - docker-compose.yml and .env present alongside this script
#   - GHCR images already pushed (this script only pulls; it never builds)

set -euo pipefail

# ── Resolve script directory (works even when called via symlink) ─────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
ENV_FILE="${SCRIPT_DIR}/.env"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[deploy] $*"; }
fail() { echo "[deploy] ERROR: $*" >&2; exit 1; }

compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

# ── Argument parsing ──────────────────────────────────────────────────────────
SKIP_MIGRATE=false
SKIP_SYNC_LOGS=false

for arg in "$@"; do
  case "$arg" in
    --skip-migrate)   SKIP_MIGRATE=true ;;
    --skip-sync-logs) SKIP_SYNC_LOGS=true ;;
    *) fail "Unknown argument: $arg" ;;
  esac
done

# ── Pre-flight ────────────────────────────────────────────────────────────────
[[ -f "$COMPOSE_FILE" ]] || fail "docker-compose.yml not found at ${COMPOSE_FILE}"
[[ -f "$ENV_FILE" ]] \
  || fail ".env not found at ${ENV_FILE}. Copy .env.compose.example and fill it in."
command -v docker >/dev/null 2>&1 \
  || fail "docker is not installed or not in PATH."
docker compose version >/dev/null 2>&1 \
  || fail "Docker Compose plugin (v2) is required. Try: apt install docker-compose-plugin"

# ── Pull all images ───────────────────────────────────────────────────────────
log "Pulling images from GHCR..."
compose pull --quiet

# ── Start postgres first and wait for it to be healthy ───────────────────────
log "Starting postgres..."
compose up -d postgres

log "Waiting for postgres to be healthy..."
RETRIES=30
until compose exec -T postgres pg_isready -U bitsyscerts >/dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  [[ $RETRIES -gt 0 ]] || fail "Postgres did not become healthy in time."
  sleep 2
done
log "Postgres is ready."

# ── One-shot init: run migrations ─────────────────────────────────────────────
if [[ "$SKIP_MIGRATE" == false ]]; then
  log "Running compose migrate service..."
  compose up --abort-on-container-exit --exit-code-from migrate migrate
  log "Migrations complete."
fi

# ── One-shot init: sync CT log list ──────────────────────────────────────────
if [[ "$SKIP_SYNC_LOGS" == false ]]; then
  log "Syncing CT log list..."
  compose run --rm migrate ctpool sync-logs
  log "CT log sync complete."
fi

log "Seeding initial stats snapshot..."
compose run --rm migrate ctpool stats-snapshot
log "Initial stats snapshot complete."

log "Running one maintenance pass..."
compose run --rm migrate ctpool maintenance
log "Initial maintenance pass complete."

# ── Bring up the full stack ───────────────────────────────────────────────────
log "Starting all services..."
if [[ "$SKIP_MIGRATE" == true ]]; then
  compose up --detach --remove-orphans --no-deps \
    api frontend backfill tail stats-snapshotter maintenance
else
  compose up --detach --remove-orphans
fi

log "Deploy complete. Stack status:"
compose ps
