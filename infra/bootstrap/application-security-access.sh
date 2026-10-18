#!/bin/sh
set -eu
: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"
bao token lookup -field=policies >/dev/null

bao policy write application-security-reader - >/dev/null <<'POLICY'
path "secret/data/brokecart/shared/jwt" {
  capabilities = ["read"]
}
path "secret/data/brokecart/shared/internal" {
  capabilities = ["read"]
}
POLICY

bao policy write identity-signing-key-reader - >/dev/null <<'POLICY'
path "secret/data/brokecart/identity/jwt" {
  capabilities = ["read"]
}
POLICY

for service in catalog pricing identity cart checkout orders inventory payments \
  payment-provider shipping returns notifications search reporting; do
  policies=application-security-reader
  if [ "$service" = identity ]; then
    policies=application-security-reader,identity-signing-key-reader
  fi
  bao write "auth/kubernetes/role/$service-application-secrets" \
    bound_service_account_names="$service-application-secrets" \
    bound_service_account_namespaces="brokecart-$service" \
    audience=vault policies="$policies" ttl=15m >/dev/null
done
echo "Application security access configured; private-key access belongs only to identity"

bao policy write maintenance-internal-reader - >/dev/null <<'POLICY'
path "secret/data/brokecart/shared/internal" {
  capabilities = ["read"]
}
POLICY
bao write auth/kubernetes/role/maintenance-application-secrets \
  bound_service_account_names=maintenance-application-secrets \
  bound_service_account_namespaces=brokecart-maintenance \
  audience=vault policies=maintenance-internal-reader ttl=15m >/dev/null
echo "Maintenance token-only access configured"
