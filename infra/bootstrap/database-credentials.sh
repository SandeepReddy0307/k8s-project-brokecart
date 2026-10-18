#!/bin/sh
set -eu

# Run inside the OpenBao container with BAO_TOKEN already exported.
: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"

create_credentials() {
  secret_path="$1"
  database_user="$2"
  database_name="$3"

  # Preserve credentials that already exist.
  if bao kv get -mount=secret "$secret_path" >/dev/null 2>&1; then
    echo "Keeping existing credentials: $secret_path"
    return
  fi

  password="$(
    bao write -field=random_bytes \
      sys/tools/random bytes=24 format=hex
  )"

  # CAS=0 permits creation only when the key has never been written.
  # It prevents accidentally replacing an existing credential.
  bao kv put -mount=secret -cas=0 "$secret_path" \
    username="$database_user" \
    password="$password" \
    database="$database_name" \
    >/dev/null

  unset password

  echo "Created credentials: $secret_path"
}

create_credentials \
  brokecart/postgres/admin \
  brokecart_admin \
  postgres

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
  database_name="$(printf '%s' "$service" | tr '-' '_')"

  create_credentials \
    "brokecart/$service/database" \
    "brokecart_$database_name" \
    "$database_name"
done

echo "Database credential bootstrap completed"
