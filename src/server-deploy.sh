#!/usr/bin/env bash
# server-deploy.sh — one-shot runtime deploy for a bare Ubuntu + Docker server.
#
# This script does NOT require the BitsyCerts source repository to be present.
# Place it in the same directory as docker-compose.yml and .env, then run it.
#
# Usage:
#   ./server-deploy.sh [--skip-migrate] [--skip-sync-logs]
#
#   --skip-migrate    Skip `alembic upgrade head`  (useful on re-deploys when
#                     the schema has not changed).
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
  || fail ".env not found at ${ENV_FILE}. Copy .env.example and fill it in."
command -v docker >/dev/null 2>&1 \
  || fail "docker is not installed or not in PATH."
docker compose version >/dev/null 2>&1 \
  || fail "Docker Compose plugin (v2) is required. Try: apt install docker-compose-plugin"

# ── Pull all images ───────────────────────────────────────────────────────────
log "Pulling images from GHCR..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull --quiet

# ── Start postgres first and wait for it to be healthy ───────────────────────
log "Starting postgres..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres

log "Waiting for postgres to be healthy..."
RETRIES=30
until docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
    exec -T postgres pg_isready -U bitsyscerts >/dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  [[ $RETRIES -gt 0 ]] || fail "Postgres did not become healthy in time."
  sleep 2
done
log "Postgres is ready."

# ── One-shot init: run migrations ─────────────────────────────────────────────
# Uses `docker compose run` so the container is automatically on the compose
# network and can reach the `postgres` service by hostname.
if [[ "$SKIP_MIGRATE" == false ]]; then
  log "Running Alembic migrations..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
    run --rm api \
    alembic -c /app/alembic.ini upgrade head
  log "Migrations complete."
fi

# ── One-shot init: sync CT log list ──────────────────────────────────────────
if [[ "$SKIP_SYNC_LOGS" == false ]]; then
  log "Syncing CT log list..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
    run --rm api \
    ctpool sync-logs
  log "CT log sync complete."
fi

# ── Bring up the full stack ───────────────────────────────────────────────────
log "Starting all services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
  up --detach --remove-orphans

log "Deploy complete. Stack status:"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
