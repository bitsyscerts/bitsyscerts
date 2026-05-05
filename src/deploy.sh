#!/usr/bin/env bash
# deploy.sh — build, migrate, seed, and bring up the BitsyCerts stack.
#
# Usage (from the repository root):
#   ./src/deploy.sh [--build] [--skip-migrate] [--skip-sync-logs]
#
#   --build           Force local image builds instead of pulling from GHCR.
#   --skip-migrate    Skip `alembic upgrade head`.
#   --skip-sync-logs  Skip `ctpool sync-logs`.
#
# Requirements:
#   - Docker Engine 25+ with the Compose plugin (docker compose v2)
#   - src/.env exists and is filled in (copy from src/.env.example)

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
[[ -f "$ENV_FILE" ]] || fail ".env not found at ${ENV_FILE}. Copy src/.env.example and fill it in."
command -v docker >/dev/null 2>&1 || fail "docker is not installed or not in PATH."
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin (v2) is required."

# Load IMAGE_TAG from .env (default: latest)
IMAGE_TAG="$(grep -E '^IMAGE_TAG=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PYTHON_IMAGE="ghcr.io/bitsyscerts/bitsyscerts-python:${IMAGE_TAG}"

log "IMAGE_TAG=${IMAGE_TAG}"

# ── Optional local build ─────────────────────────────────────────────────────
if [[ "$DO_BUILD" == true ]]; then
  log "Building Python image from source..."
  docker build \
    --file "${SRC_DIR}/api/Dockerfile" \
    --tag  "${PYTHON_IMAGE}" \
    "${REPO_ROOT}"

  log "Building frontend image from source..."
  docker build \
    --file "${SRC_DIR}/app/Dockerfile" \
    --tag  "ghcr.io/bitsyscerts/bitsyscerts-frontend:${IMAGE_TAG}" \
    "${REPO_ROOT}"
fi

# ── One-shot init containers ─────────────────────────────────────────────────
if [[ "$SKIP_MIGRATE" == false ]]; then
  log "Running Alembic migrations..."
  docker run --rm \
    --env-file "${ENV_FILE}" \
    --workdir /app \
    "${PYTHON_IMAGE}" \
    alembic upgrade head
  log "Migrations complete."
fi

if [[ "$SKIP_SYNC_LOGS" == false ]]; then
  log "Syncing CT log list..."
  docker run --rm \
    --env-file "${ENV_FILE}" \
    "${PYTHON_IMAGE}" \
    ctpool sync-logs
  log "CT log sync complete."
fi

# ── Bring up the stack ───────────────────────────────────────────────────────
log "Pulling latest images..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" pull --quiet

log "Starting services..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
  up --force-recreate --detach --remove-orphans

log "Deploy complete. Stack status:"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps
