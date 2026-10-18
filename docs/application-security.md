# Application security credentials

Identity signs login JWTs with an RSA private key. All 14 HTTP backends verify signatures with its public key. These are application keys, separate from cert-manager HTTPS certificates. The application expects a PKCS#8 PEM private key and SubjectPublicKeyInfo PEM public key; OpenSSL generates those formats here.

Internal HTTP calls also use a shared X-Internal-Token header. This is the existing application's shared-token design, not per-service authorization or mutual TLS. Keep /internal routes off the public Gateway.

## OpenBao values and access

| KV v2 path under secret | Fields | Application readers |
|---|---|---|
| brokecart/identity/jwt | private-key, public-key | Identity |
| brokecart/shared/jwt | public-key | All HTTP backends |
| brokecart/shared/internal | token | All HTTP backends |

The complete identity keypair is kept together so an interrupted bootstrap can restore the separate public-key copy. The private key is never written to either shared path.

Policy application-security-reader reads the shared paths. Identity additionally receives identity-signing-key-reader. Each backend's SERVICE-application-secrets role binds the same-named ServiceAccount in brokecart-SERVICE, audience vault, TTL 15m. Only identity gets signing-key access. Administrators retain their administrative access.

Frontend receives none of these values. Maintenance-worker now uses its own token-only role and ExternalSecret in brokecart-maintenance; rerun the bootstrap once to add that policy/role.

## Bootstrap

Run from WSL at the repository root:

```bash
bash infra/bootstrap/run-application-security-bootstrap.sh
```

The launcher needs OpenSSL, Python 3, kubectl and a running/unsealed OpenBao with the existing secret KV v2 mount and Kubernetes auth method. Enter an authorized bootstrap token at its hidden prompt.

A candidate 2048-bit RSA keypair is generated in an owner-only temporary directory under /tmp, sent through stdin, and removed by an exit trap. Generated keys and tokens are not written to Git or printed. The token is not passed as a command argument.

Existing values are retained. New values use check-and-set 0. If the identity keypair exists but the shared public copy is absent, bootstrap restores the matching public key. If the public copies disagree, it fails rather than silently rotating keys. Soft-deleted paths require deliberate recovery.

The internal token is 32 random bytes encoded as 64 hexadecimal characters without a trailing newline. Routine application CI must not use an OpenBao root token.

## Application chart

The optional security section defaults to disabled. Catalog enables it with secretName catalog-application-security, role/ServiceAccount catalog-application-secrets, and identitySigningKey=false.

This renders a ServiceAccount at Argo wave -3, SecretStore catalog-security-openbao at -2, and ExternalSecret catalog-application-security at -1. ESO materializes a Kubernetes Secret with internal-token and jwt-public-key. Catalog does not request the private key.

Identity will use its own role/ServiceAccount with identitySigningKey=true. Other roles cannot read the private path even if that Helm flag is changed.

The HTTP backend Deployment maps:

| Environment variable | Secret key |
|---|---|
| INTERNAL_TOKEN | internal-token |
| JWT_PUBLIC_KEY | jwt-public-key |
| JWT_PRIVATE_KEY, identity only | jwt-private-key |

The catalog Deployment template now wires these references; no live application deployment has been performed. ESO refresh does not update a running process's environment; credential changes require coordinated rollouts. The application does not implement overlapping JWT key rotation, and bootstrap intentionally preserves existing keys.

## Verification

```bash
helm lint infra/charts/application -f infra/values/catalog.yaml
python3 tests/application_security_configuration.py
git diff --check
```

On 2026-10-18 these checks passed. The offline test uses real OpenSSL key generation but temporary fake kubectl/OpenBao commands. It checks RSA format compatibility, preservation on rerun, rejection of mismatched public keys, 14 backend roles, a maintenance token-only role and catalog private-key exclusion. It never contacts kind or uses a real token.

Live OpenBao changes require the bootstrap command above; editing the chart alone does not create them.
