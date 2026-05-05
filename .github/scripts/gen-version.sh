#!/usr/bin/env bash
# gen-version.sh — Single source of truth for BitsysCerts build versioning.
#
# Format:
#   Main branch:   yy.mdd.hhmm                      e.g. 26.504.913
#   Other branch:  yy.mdd.hhmm+branch.sha  (PEP 440) e.g. 26.504.913+staging.abc1234
#                  yy.mdd.hhmm-branch-sha  (Docker)   e.g. 26.504.913-staging-abc1234
#
# Timestamp rules (UTC):
#   Month and hour have NO leading zero.
#   Day and minute always have a leading zero (two digits).
#
# Usage:
#   source .github/scripts/gen-version.sh
#   echo "$VERSION_DOCKER"
#
# Exports: VERSION_CORE  VERSION_PEP440  VERSION_DOCKER

set -euo pipefail

# ── Core timestamp ─────────────────────────────────────────────────────────────
# printf '%d' strips leading zeros portably (avoids GNU-only %-m / %-H).
_YY=$(date -u +%y)
_M=$(printf '%d' "$(date -u +%m)")   # month — no leading zero
_DD=$(date -u +%d)                   # day   — two digits (leading zero kept)
_H=$(printf '%d' "$(date -u +%H)")   # hour  — no leading zero
_MM=$(date -u +%M)                   # minute — two digits (leading zero kept)

VERSION_CORE="${_YY}.${_M}${_DD}.${_H}${_MM}"

# ── Branch & commit ────────────────────────────────────────────────────────────
# GITHUB_REF_NAME is set by GH Actions; fall back to git for local use.
BRANCH="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"
SHA="${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || echo 0000000)}"
SHA="${SHA:0:7}"

# Sanitize branch name:
#   / → -   (Docker tags and PEP 440 local segments forbid slashes)
BRANCH_DOCKER="${BRANCH//\//-}"
#   - → .   (PEP 440 local segment allows only [a-zA-Z0-9.])
BRANCH_PEP440="${BRANCH_DOCKER//-/.}"

# ── Compose final version strings ──────────────────────────────────────────────
if [[ "$BRANCH" == "main" ]]; then
    VERSION_PEP440="$VERSION_CORE"
    VERSION_DOCKER="$VERSION_CORE"
else
    VERSION_PEP440="${VERSION_CORE}+${BRANCH_PEP440}.${SHA}"
    VERSION_DOCKER="${VERSION_CORE}-${BRANCH_DOCKER}-${SHA}"
fi

export VERSION_CORE VERSION_PEP440 VERSION_DOCKER
