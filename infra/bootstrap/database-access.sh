#!/bin/sh
set -eu

: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"

services="
catalog
pricing
identity
cart
checkout
orders
inventory
payments
payment-provider
shipping
returns
notifications
search
reporting
"

# Confirm the existing Kubernetes auth configuration is accessible.
bao read auth/kubernetes/config >/dev/null

# 1. PostgreSQL admin credential access.
bao policy write postgres-admin-reader - >/dev/null <<'EOF'
path "secret/data/brokecart/postgres/admin" {
  capabilities = ["read"]
}
EOF

bao write auth/kubernetes/role/postgres-secrets \
  bound_service_account_names=postgres-secrets \
  bound_service_account_namespaces=brokecart-postgres \
  audience=vault \
  policies=postgres-admin-reader \
  ttl=15m \
  >/dev/null

echo "Configured PostgreSQL admin credential access"

# 2. Provisioning access to all service database credentials.
{
  for service in $services; do
    printf 'path "secret/data/brokecart/%s/database" {\n' "$service"
    printf '  capabilities = ["read"]\n'
    printf '}\n'
  done
} | bao policy write database-provisioner-reader - >/dev/null

bao write auth/kubernetes/role/database-provisioner \
  bound_service_account_names=database-provisioner \
  bound_service_account_namespaces=brokecart-postgres \
  audience=vault \
  policies=database-provisioner-reader \
  ttl=15m \
  >/dev/null

echo "Configured database provisioning credential access"

# 3. Individual application access.
for service in $services; do
  policy_name="$service-db-reader"
  role_name="$service-secrets"

  bao policy write "$policy_name" - >/dev/null <<EOF
path "secret/data/brokecart/$service/database" {
  capabilities = ["read"]
}
EOF

  bao write "auth/kubernetes/role/$role_name" \
    bound_service_account_names="$role_name" \
    bound_service_account_namespaces="brokecart-$service" \
    audience=vault \
    policies="$policy_name" \
    ttl=15m \
    >/dev/null

  echo "Configured database credential access for $service"
done

echo "Database access bootstrap completed"
