#!/usr/bin/env bash

set -euo pipefail

COMPOSE_BUNDLE=""
PYTHON_BUNDLE=""
TEMP_DIR=""

fail() {
  echo "[validate-runtime-bundles] ERROR: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-bundle)
      COMPOSE_BUNDLE="$2"
      shift 2
      ;;
    --python-bundle)
      PYTHON_BUNDLE="$2"
      shift 2
      ;;
    --temp-dir)
      TEMP_DIR="$2"
      shift 2
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$COMPOSE_BUNDLE" ]] || fail "--compose-bundle is required."
[[ -n "$PYTHON_BUNDLE" ]] || fail "--python-bundle is required."
[[ -f "$COMPOSE_BUNDLE" ]] || fail "Compose bundle not found: $COMPOSE_BUNDLE"
[[ -f "$PYTHON_BUNDLE" ]] || fail "Python bundle not found: $PYTHON_BUNDLE"
command -v docker >/dev/null 2>&1 || fail "docker is required for compose bundle validation."

extract_zip() {
  local archive_path="$1"
  local output_dir="$2"

  python - <<'PY' "$archive_path" "$output_dir"
from __future__ import annotations

import pathlib
import sys
import zipfile

archive_path = pathlib.Path(sys.argv[1])
output_dir = pathlib.Path(sys.argv[2])
output_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(archive_path) as archive:
    archive.extractall(output_dir)
PY
}

assert_runtime_file_has_no_checkout_paths() {
  local file_path="$1"

  if grep -nE '/workspaces/|src/\.env' "$file_path" >/dev/null; then
    fail "Checkout-only path leaked into bundle runtime file: $file_path"
  fi
}

assert_python_bundle_excludes_noise() {
  local bundle_root="$1"

  if find "$bundle_root" -type d \( -name node_modules -o -name coverage -o -name .venv -o -name __pycache__ \) | grep -q .; then
    fail "Python runtime bundle contains local build/cache directories."
  fi
}

TEMP_DIR="${TEMP_DIR:-$(mktemp -d)}"
trap 'rm -rf "$TEMP_DIR"' EXIT

COMPOSE_DIR="$TEMP_DIR/compose"
PYTHON_DIR="$TEMP_DIR/python"

extract_zip "$COMPOSE_BUNDLE" "$COMPOSE_DIR"
extract_zip "$PYTHON_BUNDLE" "$PYTHON_DIR"

[[ -f "$COMPOSE_DIR/docker-compose.yml" ]] || fail "Compose bundle missing docker-compose.yml"
[[ -f "$COMPOSE_DIR/server-deploy.sh" ]] || fail "Compose bundle missing server-deploy.sh"
[[ -f "$COMPOSE_DIR/.env.compose.example" ]] || fail "Compose bundle missing .env.compose.example"
[[ -f "$COMPOSE_DIR/README.md" ]] || fail "Compose bundle missing README.md"
[[ -f "$COMPOSE_DIR/docs/OPERATIONS.md" ]] || fail "Compose bundle missing docs/OPERATIONS.md"
[[ -f "$COMPOSE_DIR/LICENSE" ]] || fail "Compose bundle missing LICENSE"
[[ ! -e "$COMPOSE_DIR/src" ]] || fail "Compose bundle should not contain a source checkout tree."

assert_runtime_file_has_no_checkout_paths "$COMPOSE_DIR/docker-compose.yml"
assert_runtime_file_has_no_checkout_paths "$COMPOSE_DIR/server-deploy.sh"
assert_runtime_file_has_no_checkout_paths "$COMPOSE_DIR/.env.compose.example"

cp "$COMPOSE_DIR/.env.compose.example" "$COMPOSE_DIR/.env"
(
  cd "$COMPOSE_DIR"
  docker compose config >/dev/null
)

[[ -d "$PYTHON_DIR/src/api" ]] || fail "Python bundle missing src/api"
[[ -d "$PYTHON_DIR/src/ctpool" ]] || fail "Python bundle missing src/ctpool"
[[ -d "$PYTHON_DIR/src/app" ]] || fail "Python bundle missing src/app"
[[ -f "$PYTHON_DIR/.env.local.example" ]] || fail "Python bundle missing .env.local.example"
[[ -f "$PYTHON_DIR/.env.development.example" ]] || fail "Python bundle missing .env.development.example"
[[ -f "$PYTHON_DIR/README.md" ]] || fail "Python bundle missing README.md"
[[ -f "$PYTHON_DIR/docs/OPERATIONS.md" ]] || fail "Python bundle missing docs/OPERATIONS.md"
[[ -f "$PYTHON_DIR/docs/ARCHITECTURE.md" ]] || fail "Python bundle missing docs/ARCHITECTURE.md"

assert_python_bundle_excludes_noise "$PYTHON_DIR"

echo "[validate-runtime-bundles] Extracted runtime bundles validated successfully."