#!/bin/bash
set -euo pipefail
umask 077

node_id="${POD_NAME##*-}"
broker_host="${POD_NAME}.kafka-headless.${POD_NAMESPACE}.svc.cluster.local"

admin_user="$(cat /etc/kafka-auth/admin-username)"
admin_password="$(cat /etc/kafka-auth/admin-password)"
keystore_password="$(cat /etc/kafka-auth/keystore-password)"

validate_username() {
  case "$1" in
    ""|*[!a-zA-Z0-9_]*)
      echo "Invalid Kafka username format" >&2
      exit 1
      ;;
  esac
}

validate_password() {
  case "$1" in
    ""|*[!a-fA-F0-9]*)
      echo "Kafka password must be nonempty hexadecimal text" >&2
      exit 1
      ;;
  esac
}

validate_username "$admin_user"
validate_password "$admin_password"
validate_password "$keystore_password"

cp /etc/kafka-config/server.properties /tmp/server.properties

{
  printf '\nnode.id=%s\n' "$node_id"

  printf 'advertised.listeners=CLIENT://%s:9092,INTERNAL://%s:9094\n' \
    "$broker_host" "$broker_host"

  printf 'ssl.keystore.password=%s\n' "$keystore_password"
  printf 'ssl.key.password=%s\n' "$keystore_password"
  printf 'ssl.truststore.password=%s\n' "$keystore_password"

  printf 'super.users=User:CN=brokecart-kafka;User:%s\n' "$admin_user"

  printf 'listener.name.client.plain.sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required '

  printf 'user_%s="%s" ' "$admin_user" "$admin_password"

  for credentials in /etc/kafka-clients/*; do
    client_user="$(cat "$credentials/username")"
    client_password="$(cat "$credentials/password")"

    validate_username "$client_user"
    validate_password "$client_password"

    printf 'user_%s="%s" ' "$client_user" "$client_password"
  done

  printf ';\n'
} >> /tmp/server.properties

unset admin_password keystore_password client_password

if [ -f /var/lib/kafka/data/meta.properties ]; then
  grep -Fxq "cluster.id=$CLUSTER_ID" \
    /var/lib/kafka/data/meta.properties || {
      echo "Stored Kafka cluster ID does not match configuration" >&2
      exit 1
    }

  grep -Fxq "node.id=$node_id" \
    /var/lib/kafka/data/meta.properties || {
      echo "Stored Kafka node ID does not match this Pod" >&2
      exit 1
    }
fi

/opt/kafka/bin/kafka-storage.sh format \
  --ignore-formatted \
  --cluster-id "$CLUSTER_ID" \
  --config /tmp/server.properties

exec /opt/kafka/bin/kafka-server-start.sh /tmp/server.properties
