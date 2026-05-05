#!/usr/bin/env bash
# install-hooks.sh — point Git at the committed hooks in .github/hooks/.
#
# Run once after cloning:
#   ./src/install-hooks.sh
#
# This tells Git to use .github/hooks/ as the hooks directory instead of
# the default .git/hooks/, so the pre-commit lint checks stay in version
# control and everyone on the team gets them automatically.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Make the hook executable (git clone may not preserve the bit)
chmod +x "$REPO_ROOT/.github/hooks/pre-commit"

git -C "$REPO_ROOT" config core.hooksPath .github/hooks

echo "Git hooks installed. Pre-commit linting is now active."
echo "Hooks directory: .github/hooks/"
