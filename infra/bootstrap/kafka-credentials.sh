#!/bin/sh
set -eu

: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"

# Fail early if the supplied token is rejected.
bao token lookup -field=policies >/dev/null

random_password() {
  bao write -field=random_bytes \
    sys/tools/random bytes=24 format=hex
}

create_login() {
  secret_path="$1"
  login_name="$2"

  if bao kv get -mount=secret "$secret_path" >/dev/null 2>&1; then
    echo "Keeping existing credentials: $secret_path"
    return
  fi

  password="$(random_password)"

  bao kv put -mount=secret -cas=0 "$secret_path" \
    username="$login_name" \
    password="$password" \
    >/dev/null

  unset password

  echo "Created credentials: $secret_path"
}

# 1. Password protecting Kafka's certificate keystore.
if bao kv get -mount=secret brokecart/kafka/broker >/dev/null 2>&1; then
  echo "Keeping existing Kafka keystore credentials"
else
  keystore_password="$(random_password)"

  bao kv put -mount=secret -cas=0 brokecart/kafka/broker \
    keystore-password="$keystore_password" \
    >/dev/null

  unset keystore_password

  echo "Created Kafka keystore credentials"
fi

# 2. Kafka administrator.
create_login brokecart/kafka/admin kafka_admin

# Kafka UI has separate browser and read-only Kafka credentials.
create_login brokecart/kafka-ui/auth kafka_viewer
create_login brokecart/kafka-ui/kafka brokecart_kafka_ui

# 3. Individual application logins.
for service in \
  catalog \
  pricing \
  identity \
  cart \
  checkout \
  orders \
  inventory \
  payments \
  payment-provider \
  shipping \
  returns \
  notifications \
  search \
  reporting
do
  login_suffix="$(printf '%s' "$service" | tr '-' '_')"

  create_login \
    "brokecart/$service/kafka" \
    "brokecart_$login_suffix"
done

echo "Kafka credential bootstrap completed"
