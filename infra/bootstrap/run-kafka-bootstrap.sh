#!/bin/bash
# Run from WSL. The token is read privately and sent only through stdin.
set -euo pipefail

bootstrap_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

for script in kafka-credentials.sh kafka-access.sh; do
  test -r "$bootstrap_dir/$script"
  sh -n "$bootstrap_dir/$script"
done

read -r -s -p 'OpenBao bootstrap token: ' bootstrap_token
printf '\n'
trap 'unset bootstrap_token' EXIT
test -n "$bootstrap_token" || {
  echo "A bootstrap token is required" >&2
  exit 1
}

{
  printf '%s\n' "$bootstrap_token"
  cat "$bootstrap_dir/kafka-credentials.sh"
  printf '\n'
  cat "$bootstrap_dir/kafka-access.sh"
  printf '\n'
} | kubectl --context kind-brokecart -n openbao exec -i openbao-0 -- \
  /bin/sh -c 'IFS= read -r BAO_TOKEN; export BAO_TOKEN; exec /bin/sh -s'

echo "Kafka bootstrap finished; the temporary authenticated process has exited."
