#!/bin/sh
# docker-entrypoint.sh — generates /usr/share/nginx/html/env-config.js from
# container environment variables at startup, then hands off to nginx.
#
# This lets operators set BANNER_* variables in docker-compose.yml (or their
# .env file) without rebuilding the frontend image.
#
# Supported variables (all optional, defaults shown):
#   BANNER_VISIBLE=false
#   BANNER_TEXT=
#   BANNER_SEVERITY=info
#   BANNER_ICON=InfoCircle
set -eu

BANNER_VISIBLE="${BANNER_VISIBLE:-false}"
BANNER_TEXT="${BANNER_TEXT:-}"
BANNER_SEVERITY="${BANNER_SEVERITY:-info}"
BANNER_ICON="${BANNER_ICON:-InfoCircle}"

# Minimal JS-string escaping: backslashes then double-quotes.
# Keeps the generated file valid even if an operator uses quotes in the text.
escape_js() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

cat > /usr/share/nginx/html/env-config.js <<JS
// Runtime environment — generated at container start by docker-entrypoint.sh.
// Do not edit; changes will be overwritten on the next container restart.
window.__ENV__ = {
  BANNER_VISIBLE: "$(escape_js "$BANNER_VISIBLE")",
  BANNER_TEXT: "$(escape_js "$BANNER_TEXT")",
  BANNER_SEVERITY: "$(escape_js "$BANNER_SEVERITY")",
  BANNER_ICON: "$(escape_js "$BANNER_ICON")"
};
JS

exec nginx -g "daemon off;"
