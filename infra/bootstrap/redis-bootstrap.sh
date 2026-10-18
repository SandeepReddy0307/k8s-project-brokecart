#!/bin/sh
set -eu

: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"

# 1. Create the password if it does not already exist.
if bao kv get -mount=secret brokecart/redis/auth >/dev/null 2>&1; then
  echo "Keeping existing Redis credentials"
else
  password="$(
    bao write -field=random_bytes \
      sys/tools/random bytes=24 format=hex
  )"

  bao kv put -mount=secret -cas=0 brokecart/redis/auth \
    password="$password" \
    >/dev/null

  unset password
  echo "Created Redis credentials"
fi

# 2. Allow reading only this Redis credential.
bao policy write redis-auth-reader - >/dev/null <<'EOF'
path "secret/data/brokecart/redis/auth" {
  capabilities = ["read"]
}
EOF

# 3. Redis server credential delivery.
bao write auth/kubernetes/role/redis-secrets \
  bound_service_account_names=redis-secrets \
  bound_service_account_namespaces=brokecart-redis \
  audience=vault \
  policies=redis-auth-reader \
  ttl=15m \
  >/dev/null

# 4. Cart application credential delivery.
bao write auth/kubernetes/role/cart-redis-secrets \
  bound_service_account_names=cart-redis-secrets \
  bound_service_account_namespaces=brokecart-cart \
  audience=vault \
  policies=redis-auth-reader \
  ttl=15m \
  >/dev/null

echo "Redis credential and access bootstrap completed"
