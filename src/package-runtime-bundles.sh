#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/dist"
VERSION="dev"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

copy_file_into_bundle() {
  local source_path="$1"
  local bundle_root="$2"
  local target_path="$3"

  mkdir -p "$(dirname "${bundle_root}/${target_path}")"
  cp "${source_path}" "${bundle_root}/${target_path}"
}

copy_tracked_tree_into_bundle() {
  local source_prefix="$1"
  local bundle_root="$2"

  while IFS= read -r relative_path; do
    mkdir -p "$(dirname "${bundle_root}/${relative_path}")"
    cp "${ROOT_DIR}/${relative_path}" "${bundle_root}/${relative_path}"
  done < <(git -C "${ROOT_DIR}" ls-files "${source_prefix}")
}

zip_bundle() {
  local bundle_root="$1"
  local output_zip="$2"

  python - <<'PY' "$bundle_root" "$output_zip"
from __future__ import annotations

import pathlib
import sys
import zipfile

bundle_root = pathlib.Path(sys.argv[1])
output_zip = pathlib.Path(sys.argv[2])
output_zip.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(bundle_root.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(bundle_root))
PY
}

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

COMPOSE_ROOT="${TEMP_DIR}/compose"
LOCAL_ROOT="${TEMP_DIR}/python"
mkdir -p "$COMPOSE_ROOT" "$LOCAL_ROOT"

copy_file_into_bundle "${ROOT_DIR}/src/docker-compose.yml" "$COMPOSE_ROOT" "docker-compose.yml"
copy_file_into_bundle "${ROOT_DIR}/src/server-deploy.sh" "$COMPOSE_ROOT" "server-deploy.sh"
copy_file_into_bundle "${ROOT_DIR}/src/.env.compose.example" "$COMPOSE_ROOT" ".env.compose.example"
copy_file_into_bundle "${ROOT_DIR}/README.md" "$COMPOSE_ROOT" "README.md"
copy_file_into_bundle "${ROOT_DIR}/docs/OPERATIONS.md" "$COMPOSE_ROOT" "docs/OPERATIONS.md"
copy_file_into_bundle "${ROOT_DIR}/LICENSE" "$COMPOSE_ROOT" "LICENSE"

copy_tracked_tree_into_bundle "src/api" "$LOCAL_ROOT"
copy_tracked_tree_into_bundle "src/ctpool" "$LOCAL_ROOT"
copy_tracked_tree_into_bundle "src/app" "$LOCAL_ROOT"
copy_file_into_bundle "${ROOT_DIR}/src/.env.local.example" "$LOCAL_ROOT" ".env.local.example"
copy_file_into_bundle "${ROOT_DIR}/src/.env.development.example" "$LOCAL_ROOT" ".env.development.example"
copy_file_into_bundle "${ROOT_DIR}/README.md" "$LOCAL_ROOT" "README.md"
copy_file_into_bundle "${ROOT_DIR}/docs/OPERATIONS.md" "$LOCAL_ROOT" "docs/OPERATIONS.md"
copy_file_into_bundle "${ROOT_DIR}/docs/ARCHITECTURE.md" "$LOCAL_ROOT" "docs/ARCHITECTURE.md"
copy_file_into_bundle "${ROOT_DIR}/LICENSE" "$LOCAL_ROOT" "LICENSE"

zip_bundle "$COMPOSE_ROOT" "${OUTPUT_DIR}/bitsyscerts-compose-${VERSION}.zip"
zip_bundle "$LOCAL_ROOT" "${OUTPUT_DIR}/bitsyscerts-python-${VERSION}.zip"

echo "Created runtime bundles in ${OUTPUT_DIR}" 
