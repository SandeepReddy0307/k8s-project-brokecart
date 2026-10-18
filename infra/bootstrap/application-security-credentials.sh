#!/bin/sh
set -eu
: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"
: "${JWT_KEYPAIR_B64:?Use run-application-security-bootstrap.sh}"
bao token lookup -field=policies >/dev/null

# Store a complete keypair together first. A rerun can recover a missing public
# copy without generating a private/public mismatch.
if bao kv get -mount=secret brokecart/identity/jwt >/dev/null 2>&1; then
  echo "Keeping existing identity signing keys"
else
  printf '%s' "$JWT_KEYPAIR_B64" | base64 -d \
    | bao kv put -mount=secret -cas=0 brokecart/identity/jwt - >/dev/null
  echo "Created identity signing keys"
fi
unset JWT_KEYPAIR_B64

public_key="$(bao kv get -mount=secret -field=public-key brokecart/identity/jwt)"
if bao kv get -mount=secret brokecart/shared/jwt >/dev/null 2>&1; then
  existing_public="$(bao kv get -mount=secret -field=public-key brokecart/shared/jwt)"
  if [ "$existing_public" != "$public_key" ]; then
    echo "Stored JWT public keys disagree; reconcile deliberately before proceeding" >&2
    exit 1
  fi
  unset existing_public
  echo "Keeping existing shared JWT public key"
else
  printf '%s' "$public_key" \
    | bao kv put -mount=secret -cas=0 brokecart/shared/jwt public-key=- >/dev/null
  echo "Created shared JWT public key"
fi
unset public_key

if bao kv get -mount=secret brokecart/shared/internal >/dev/null 2>&1; then
  echo "Keeping existing internal service token"
else
  internal_token="$(bao write -field=random_bytes sys/tools/random bytes=32 format=hex)"
  printf '%s' "$internal_token" \
    | bao kv put -mount=secret -cas=0 brokecart/shared/internal token=- >/dev/null
  unset internal_token
  echo "Created internal service token"
fi
