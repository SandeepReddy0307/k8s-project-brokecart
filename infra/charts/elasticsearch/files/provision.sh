#!/bin/sh
set -eu
umask 077
endpoint="${ELASTICSEARCH_URL:-https://elasticsearch:9200}"
ca="${ELASTICSEARCH_CA:-/tls/ca.crt}"
auth_dir="${ELASTICSEARCH_AUTH_DIR:-/auth}"
admin_password="$(cat "$auth_dir/admin/password")"
search_user="$(cat "$auth_dir/search/username")"
search_password="$(cat "$auth_dir/search/password")"
case "$admin_password" in ""|*[!a-fA-F0-9]*) echo "Invalid administrator password format" >&2; exit 1 ;; esac
case "$search_password" in ""|*[!a-fA-F0-9]*) echo "Invalid search password format" >&2; exit 1 ;; esac
case "$search_user" in brokecart_search) ;; *) echo "Unexpected search username" >&2; exit 1 ;; esac
printf 'user = "elastic:%s"\n' "$admin_password" > /tmp/provision-curl.conf
unset admin_password
request() {
  curl --silent --show-error --fail --connect-timeout 3 --max-time 20 \
    --config /tmp/provision-curl.conf --cacert "$ca" \
    -H 'Content-Type: application/json' "$@"
}
attempt=0
until request "$endpoint/_cluster/health?wait_for_status=yellow&timeout=5s" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then echo "Elasticsearch is not ready" >&2; exit 1; fi
  echo "Waiting for Elasticsearch"
  sleep 5
done
# Only this index is granted. No cluster or security administration rights.
request -X PUT "$endpoint/_security/role/brokecart_search" --data-binary @/scripts/search-role.json >/dev/null
printf '{"password":"%s","roles":["brokecart_search"],"enabled":true}\n' "$search_password" > /tmp/search-user.json
unset search_password
request -X PUT "$endpoint/_security/user/$search_user" --data-binary @/tmp/search-user.json >/dev/null
rm -f /tmp/search-user.json
# Check existence explicitly: authorization/server errors must not be mistaken for a missing index.
status="$(curl --silent --show-error --connect-timeout 3 --max-time 20 \
  --config /tmp/provision-curl.conf --cacert "$ca" \
  --output /dev/null --write-out '%{http_code}' "$endpoint/brokecart-products")"
case "$status" in
  200) echo "Keeping existing product index" ;;
  404) request -X PUT "$endpoint/brokecart-products" --data-binary @/scripts/product-index.json >/dev/null ;;
  *) echo "Cannot inspect product index (HTTP $status)" >&2; exit 1 ;;
esac
rm -f /tmp/provision-curl.conf
echo "Elasticsearch search user, restricted role and product index are ready"
