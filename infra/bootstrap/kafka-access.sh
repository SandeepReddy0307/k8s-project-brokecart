#!/bin/sh
set -eu

: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"

bao token lookup -field=policies >/dev/null

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

# 1. Kafka server credential access.
{
  cat <<'EOF'
path "secret/data/brokecart/kafka/broker" {
  capabilities = ["read"]
}

path "secret/data/brokecart/kafka/admin" {
  capabilities = ["read"]
}

path "secret/data/brokecart/kafka-ui/kafka" {
  capabilities = ["read"]
}
EOF

  for service in $services; do
    printf 'path "secret/data/brokecart/%s/kafka" {\n' "$service"
    printf '  capabilities = ["read"]\n'
    printf '}\n'
  done
} | bao policy write kafka-server-reader - >/dev/null

bao write auth/kubernetes/role/kafka-secrets \
  bound_service_account_names=kafka-secrets \
  bound_service_account_namespaces=brokecart-kafka \
  audience=vault \
  policies=kafka-server-reader \
  ttl=15m \
  >/dev/null

echo "Configured Kafka server credential access"

# 2. Individual application credential access.
for service in $services; do
  policy_name="$service-kafka-reader"
  role_name="$service-kafka-secrets"

  bao policy write "$policy_name" - >/dev/null <<EOF
path "secret/data/brokecart/$service/kafka" {
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

  echo "Configured Kafka credential access for $service"
done

# The UI may read its own browser login and Kafka login, never broker/admin secrets.
bao policy write kafka-ui-reader - >/dev/null <<'EOF'
path "secret/data/brokecart/kafka-ui/auth" {
  capabilities = ["read"]
}

path "secret/data/brokecart/kafka-ui/kafka" {
  capabilities = ["read"]
}
EOF

bao write auth/kubernetes/role/kafka-ui-secrets \
  bound_service_account_names=kafka-ui-secrets \
  bound_service_account_namespaces=brokecart-kafka-ui \
  audience=vault \
  policies=kafka-ui-reader \
  ttl=15m \
  >/dev/null

echo "Configured Kafka UI credential access"

echo "Kafka access bootstrap completed"
