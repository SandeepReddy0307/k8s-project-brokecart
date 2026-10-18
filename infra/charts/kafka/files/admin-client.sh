#!/bin/bash
# Source this file to prepare the Kafka administrative client configuration.
set -euo pipefail
umask 077

auth_dir="${KAFKA_AUTH_DIR:-/etc/kafka-auth}"
tls_dir="${KAFKA_TLS_DIR:-/etc/kafka-tls}"
export CLIENT_CONFIG="${CLIENT_CONFIG:-/tmp/kafka-admin.properties}"

admin_user="$(cat "$auth_dir/admin-username")"
admin_password="$(cat "$auth_dir/admin-password")"
keystore_password="$(cat "$auth_dir/keystore-password")"

case "$admin_user" in
  ""|*[!a-zA-Z0-9_]*)
    echo "Invalid Kafka administrator username format" >&2
    exit 1
    ;;
esac

for password_value in "$admin_password" "$keystore_password"; do
  case "$password_value" in
    ""|*[!a-fA-F0-9]*)
      echo "Kafka passwords must be nonempty hexadecimal values" >&2
      exit 1
      ;;
  esac
done

test -r "$tls_dir/truststore.p12"

{
  printf '%s\n' 'security.protocol=SASL_SSL'
  printf '%s\n' 'sasl.mechanism=PLAIN'
  printf '%s\n' 'ssl.truststore.type=PKCS12'
  printf 'ssl.truststore.location=%s/truststore.p12\n' "$tls_dir"
  printf 'ssl.truststore.password=%s\n' "$keystore_password"
  printf '%s\n' 'ssl.endpoint.identification.algorithm=https'
  printf 'sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="%s" password="%s";\n' \
    "$admin_user" "$admin_password"
} > "$CLIENT_CONFIG"

unset admin_user admin_password keystore_password password_value auth_dir tls_dir
