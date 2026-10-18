#!/bin/sh
set -eu
: "${BAO_TOKEN:?Authenticate to OpenBao before running this script}"
bao token lookup -field=policies >/dev/null
bao policy write elasticsearch-secrets-reader - >/dev/null <<'POLICY'
path "secret/data/brokecart/elasticsearch/admin" {
  capabilities = ["read"]
}
path "secret/data/brokecart/search/elasticsearch" {
  capabilities = ["read"]
}
POLICY
bao write auth/kubernetes/role/elasticsearch-secrets \
  bound_service_account_names=elasticsearch-secrets \
  bound_service_account_namespaces=brokecart-elasticsearch \
  audience=vault policies=elasticsearch-secrets-reader ttl=15m >/dev/null

bao policy write search-elasticsearch-reader - >/dev/null <<'POLICY'
path "secret/data/brokecart/search/elasticsearch" {
  capabilities = ["read"]
}
POLICY
bao write auth/kubernetes/role/search-elasticsearch-secrets \
  bound_service_account_names=search-elasticsearch-secrets \
  bound_service_account_namespaces=brokecart-search \
  audience=vault policies=search-elasticsearch-reader ttl=15m >/dev/null
echo "Elasticsearch and search credential access configured"
