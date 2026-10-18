#!/bin/sh
set -eu
: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"
bao token lookup -field=policies >/dev/null
create_login() {
  credential_path="$1"
  login_name="$2"
  if bao kv get -mount=secret "$credential_path" >/dev/null 2>&1; then
    echo "Keeping existing credentials: $credential_path"
    return
  fi
  password="$(bao write -field=random_bytes sys/tools/random bytes=24 format=hex)"
  bao kv put -mount=secret -cas=0 "$credential_path" username="$login_name" password="$password" >/dev/null
  unset password
  echo "Created credentials: $credential_path"
}
create_login brokecart/elasticsearch/admin elastic
create_login brokecart/search/elasticsearch brokecart_search
