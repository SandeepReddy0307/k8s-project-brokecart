#!/bin/sh
set -eu
umask 077
password="$(cat /auth/admin/password)"
case "$password" in ""|*[!a-fA-F0-9]*) exit 1 ;; esac
printf 'user = "elastic:%s"\n' "$password" > /tmp/readiness-curl.conf
unset password
exec curl --silent --fail --show-error --connect-timeout 2 --max-time 5 \
  --config /tmp/readiness-curl.conf --cacert /usr/share/elasticsearch/config/tls/ca.crt \
  "https://elasticsearch:9200/_cluster/health?wait_for_status=yellow&timeout=2s" \
  --output /dev/null
