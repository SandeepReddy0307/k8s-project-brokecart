#!/bin/bash
# Run from the repository root in WSL. No key material is written into Git.
set -euo pipefail
umask 077
bootstrap_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for script in application-security-credentials.sh application-security-access.sh; do
  test -r "$bootstrap_dir/$script"
  sh -n "$bootstrap_dir/$script"
done
command -v openssl >/dev/null
command -v python3 >/dev/null
read -r -s -p 'OpenBao bootstrap token: ' bootstrap_token
printf '\n'
test -n "$bootstrap_token" || { echo "A bootstrap token is required" >&2; exit 1; }
bootstrap_tmp="$(mktemp -d /tmp/brokecart-application-security.XXXXXX)"
cleanup() {
  rm -f "$bootstrap_tmp/private.pem" "$bootstrap_tmp/public.pem"
  rmdir "$bootstrap_tmp"
  unset bootstrap_token keypair_b64
}
trap cleanup EXIT
# A candidate pair is discarded if OpenBao already contains a signing key.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
  -out "$bootstrap_tmp/private.pem" 2>/dev/null
openssl pkey -in "$bootstrap_tmp/private.pem" -pubout \
  -out "$bootstrap_tmp/public.pem"
keypair_b64="$(python3 - "$bootstrap_tmp/private.pem" "$bootstrap_tmp/public.pem" <<'PY'
import base64, json, pathlib, sys
payload = {"private-key": pathlib.Path(sys.argv[1]).read_text(),
           "public-key": pathlib.Path(sys.argv[2]).read_text()}
print(base64.b64encode(json.dumps(payload).encode()).decode())
PY
)"
{
  printf '%s\n' "$bootstrap_token"
  # Base64 has no shell quotes or metacharacters; only this stdin stream carries it.
  printf "JWT_KEYPAIR_B64='%s'\n" "$keypair_b64"
  cat "$bootstrap_dir/application-security-credentials.sh"
  printf '\n'
  cat "$bootstrap_dir/application-security-access.sh"
  printf '\n'
} | kubectl --context kind-brokecart -n openbao exec -i openbao-0 -- \
  /bin/sh -c 'IFS= read -r BAO_TOKEN; export BAO_TOKEN; exec /bin/sh -s'
echo "Application security bootstrap completed"
