#!/usr/bin/env bash
# deploy.sh — build, migrate, seed, and bring up the BitsyCerts stack.
#
# Usage (from the repository root):
#   ./src/deploy.sh [--build] [--skip-migrate] [--skip-sync-logs]
#
#   --build           Force local image builds instead of pulling from GHCR.
#   --skip-migrate    Skip the compose-native `migrate` bootstrap step.
#   --skip-sync-logs  Skip `ctpool sync-logs`.
#
# Requirements:
#   - Docker Engine 25+ with the Compose plugin (docker compose v2)
#   - src/.env exists and is filled in (copy from src/.env.compose.example)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${REPO_ROOT}/src"
COMPOSE_FILE="${SRC_DIR}/docker-compose.yml"
ENV_FILE="${SRC_DIR}/.env"

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo "[deploy] $*"; }
fail() { echo "[deploy] ERROR: $*" >&2; exit 1; }

# ── Argument parsing ─────────────────────────────────────────────────────────
DO_BUILD=false
SKIP_MIGRATE=false
SKIP_SYNC_LOGS=false

for arg in "$@"; do
  case "$arg" in
    --build)          DO_BUILD=true ;;
    --skip-migrate)   SKIP_MIGRATE=true ;;
    --skip-sync-logs) SKIP_SYNC_LOGS=true ;;
    *) fail "Unknown argument: $arg" ;;
  esac
done

# ── Pre-flight ───────────────────────────────────────────────────────────────
[[ -f "$ENV_FILE" ]] || fail ".env not found at ${ENV_FILE}. Copy src/.env.compose.example and fill it in."
command -v docker >/dev/null 2>&1 || fail "docker is not installed or not in PATH."
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin (v2) is required."

# Load IMAGE_TAG from .env (default: latest)
IMAGE_TAG="$(grep -E '^IMAGE_TAG=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
IMAGE_TAG="${IMAGE_TAG:-latest}"
API_IMAGE="ghcr.io/bitsyscerts/bitsyscerts-api:${IMAGE_TAG}"
FRONTEND_IMAGE="ghcr.io/bitsyscerts/bitsyscerts-app:${IMAGE_TAG}"

compose() {
  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
}

wait_for_postgres() {
  local retries=30
  until compose exec -T postgres pg_isready -U bitsyscerts >/dev/null 2>&1; do
    retries=$((retries - 1))
    [[ $retries -gt 0 ]] || fail "Postgres did not become healthy in time."
    sleep 2
  done
}

log "IMAGE_TAG=${IMAGE_TAG}"

# ── Optional local build ─────────────────────────────────────────────────────
if [[ "$DO_BUILD" == true ]]; then
  log "Building API image from source..."
  docker build \
    --file "${SRC_DIR}/api/Dockerfile" \
    --tag  "${API_IMAGE}" \
    "${REPO_ROOT}"

  log "Building frontend image from source..."
  docker build \
    --file "${SRC_DIR}/app/Dockerfile" \
    --tag  "${FRONTEND_IMAGE}" \
    "${REPO_ROOT}"
else
  log "Pulling latest images..."
  compose pull --quiet
fi

# ── Compose-native bootstrap ─────────────────────────────────────────────────
log "Starting postgres..."
compose up -d postgres

log "Waiting for postgres to be healthy..."
wait_for_postgres
log "Postgres is ready."

if [[ "$SKIP_MIGRATE" == false ]]; then
  log "Running compose migrate service..."
  compose up --abort-on-container-exit --exit-code-from migrate migrate
  log "Migrations complete."
fi

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

# ── Bring up the stack ───────────────────────────────────────────────────────
log "Starting services..."
if [[ "$SKIP_MIGRATE" == true ]]; then
  compose up --force-recreate --detach --remove-orphans --no-deps \
    api frontend backfill tail stats-snapshotter maintenance
else
  compose up --force-recreate --detach --remove-orphans
fi

log "Deploy complete. Stack status:"
compose ps
