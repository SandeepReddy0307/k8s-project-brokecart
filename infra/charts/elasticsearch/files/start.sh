#!/bin/bash
set -euo pipefail
# Projected Secrets use fsGroup-readable permissions; the official *_FILE
# option requires owner-only permissions, so load the value before entrypoint.
ELASTIC_PASSWORD="$(cat /auth/admin/password)"
case "$ELASTIC_PASSWORD" in
  ""|*[!a-fA-F0-9]*) echo "Invalid administrator password format" >&2; exit 1 ;;
esac
export ELASTIC_PASSWORD
exec /bin/tini -- /usr/local/bin/docker-entrypoint.sh eswrapper
