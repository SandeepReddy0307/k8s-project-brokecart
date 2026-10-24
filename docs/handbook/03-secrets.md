# 3. OpenBao, identities and External Secrets

[Index](README.md) · [Previous](02-platform.md) · [Next: observability](04-observability.md)

## First understand the four separate things

Think of OpenBao as a locked credential cabinet, an OpenBao policy as the allowed drawers, an OpenBao role as the rule identifying a visitor, and ESO as the delivery worker. The application reads the delivered Kubernetes Secret; it does not need the cabinet's administrator token.

| Item | Where it exists | What it does |
|---|---|---|
| ServiceAccount `catalog-secrets` | Kubernetes, namespace `brokecart-catalog` | Identity ESO requests a short-lived Kubernetes JWT for |
| OpenBao role `catalog-secrets` | `auth/kubernetes/role/catalog-secrets` in OpenBao | Binds that exact account and namespace to a policy |
| Policy `catalog-db-reader` | OpenBao | Permits reads from Catalog's credential path only |
| SecretStore `openbao` | Kubernetes, Catalog namespace | Provider URL, CA trust, auth mount, role/account/audience |
| ExternalSecret `catalog-database-credentials` | Kubernetes, Catalog namespace | Specifies which remote fields become which Secret keys |
| Secret `catalog-database-credentials` | Kubernetes, Catalog namespace | Contains `username`, `password`, `database` for the Pod |

An OpenBao role is not a Kubernetes Role. Kubernetes RBAC controls Kubernetes API access; OpenBao policies control OpenBao path access. Similar names were chosen for clarity, not because they are the same object.

## Install OpenBao

Prerequisites: cert-manager, `brokecart-local-ca`, Gateway API and Kong from chapter 2.

```bash
helm template openbao openbao/openbao --version 0.30.4 \
  --namespace openbao -f infra/platform/openbao-values.yaml \
  > /tmp/brokecart-openbao-rendered.yaml

helm upgrade --install openbao openbao/openbao \
  --version 0.30.4 --kube-context kind-brokecart \
  --namespace openbao --create-namespace \
  -f infra/platform/openbao-values.yaml

kubectl --context kind-brokecart -n openbao \
  wait --for=condition=Ready certificate/openbao-server --timeout=120s
kubectl --context kind-brokecart -n openbao get pods,pvc,certificate
kubectl --context kind-brokecart -n openbao exec openbao-0 -- bao status
```

Do not make this first install wait for Pod readiness: a fresh server is not initialized/unsealed yet. `bao status` commonly exits 2 when sealed; this is expected state information, not proof the CLI is broken.

### Values explained

- `tlsDisable: false`: OpenBao's own API uses TLS.
- `dev.enabled: false`: state is not a disposable development-mode server.
- Injector disabled: we use ESO, not a sidecar injector for application secrets.
- Raft enabled, one replica: persistent consensus storage format, but no actual multi-node HA.
- `dataStorage`: a 2Gi PVC stores encrypted OpenBao state.
- `apiAddr`: advertised API URL `https://openbao.openbao.svc:8200`.
- Raft data path `/openbao/data`; TLS keypair mounted read-only at `/openbao/tls`.
- `BAO_CACERT`: lets the CLI validate the local API certificate.
- `disable_mlock`: accommodates the non-privileged local container environment.
- `extraObjects`: Helm also creates `Certificate/openbao-server`; cert-manager creates its TLS Secret.

## Initialize once, unseal after every restart

**Fresh, uninitialized server only:** initialize with three Shamir shares, requiring two distinct shares to unseal. Never initialize an existing server again or replace its persistent volume to “fix” a seal.

Save the initialization result outside Git with private permissions:

```bash
mkdir -p "$HOME/.local/share/brokecart-secrets"
chmod 700 "$HOME/.local/share/brokecart-secrets"

(
  umask 077
  set -o noclobber
  kubectl --context kind-brokecart -n openbao exec openbao-0 -- \
    bao operator init -key-shares=3 -key-threshold=2 -format=json \
    > "$HOME/.local/share/brokecart-secrets/openbao-init.json"
)
```

`noclobber` refuses to overwrite an existing file. Check that initialization succeeded; a failed command can leave an empty output file. Keep an offline protected backup of valid initialization material. Never commit it, show it in CI output or paste it into chat.

The file contains `unseal_keys_b64` and `root_token`. Those have different purposes. Unseal keys unlock storage; the root token authorizes administrative API operations after the server is unsealed.

Open the file locally when needed:

```bash
nano "$HOME/.local/share/brokecart-secrets/openbao-init.json"
```

Run the following command twice and enter a **different** unseal key each time at its hidden prompt:

```bash
kubectl --context kind-brokecart -n openbao \
  exec -it openbao-0 -- bao operator unseal
```

Then:

```bash
kubectl --context kind-brokecart -n openbao exec openbao-0 -- bao status
kubectl --context kind-brokecart -n openbao \
  wait --for=condition=Ready pod/openbao-0 --timeout=120s
```

Expect `Initialized: true`, `Sealed: false`, `HA Mode: active`. This project has manual unseal; ordinary process/container/laptop restarts can seal the server again. Auto-unseal is a separate design exercise.

## Enable the secret engine and Kubernetes auth

Enter the OpenBao container and authenticate privately:

```bash
kubectl --context kind-brokecart -n openbao exec -it openbao-0 -- /bin/sh
```

The next commands run **inside that shell**:

```sh
printf 'OpenBao bootstrap token: '
read -s -r BAO_TOKEN
printf '\n'
export BAO_TOKEN
bao token lookup -field=policies
bao secrets list
bao auth list
```

Export matters: `sh /tmp/script.sh` is a child process and does not inherit a shell variable unless it is exported. A blank, invalid or expired token produces permission errors even when OpenBao itself is unsealed.

On a fresh server where `secret/` and `kubernetes/` do not already exist:

```sh
bao secrets enable -path=secret kv-v2
bao auth enable kubernetes
bao write auth/kubernetes/config \
  kubernetes_host=https://kubernetes.default.svc:443 \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
```

OpenBao can use its locally mounted service-account token to call Kubernetes TokenReview when no static reviewer token is supplied. The installed chart created ClusterRoleBinding `openbao-openbao-server-binding`, binding the OpenBao ServiceAccount to `system:auth-delegator`. This is a platform API permission, not access to business database Secrets. Verify it from another WSL terminal:

```bash
kubectl --context kind-brokecart get clusterrolebinding openbao-openbao-server-binding -o yaml
```

Do not re-enable an already-mounted engine/auth path; inspect it instead. `kv-v2` versioning is why policy paths contain `secret/data/...`, while `bao kv get -mount=secret brokecart/catalog/database` hides that API prefix.

Exit the temporary admin shell after configuration:

```sh
unset BAO_TOKEN
exit
```

## Install ESO

```bash
helm upgrade --install external-secrets external-secrets/external-secrets \
  --version 2.13.0 --kube-context kind-brokecart \
  --namespace external-secrets --create-namespace \
  -f infra/platform/external-secrets-values.yaml --wait --timeout 10m

kubectl --context kind-brokecart -n external-secrets get deployments,pods
kubectl --context kind-brokecart get crd \
  externalsecrets.external-secrets.io secretstores.external-secrets.io
```

This installs the main controller, webhook and certificate controller. Our manifests use `external-secrets.io/v1`. The provider field is named `vault` because ESO uses a Vault-compatible API provider for OpenBao; this does not mean HashiCorp Vault was separately installed.

## Bootstrap database and Redis credentials

Run the checked-in scripts; do not manually paste 14 passwords into Helm values. These scripts preserve existing credentials and use create-only writes for new paths. They need an appropriately privileged bootstrap token; it is not supplied to application CI.

From WSL repository root:

```bash
kubectl --context kind-brokecart -n openbao cp \
  infra/bootstrap/database-credentials.sh openbao-0:/tmp/database-credentials.sh
kubectl --context kind-brokecart -n openbao cp \
  infra/bootstrap/database-access.sh openbao-0:/tmp/database-access.sh
kubectl --context kind-brokecart -n openbao cp \
  infra/bootstrap/redis-bootstrap.sh openbao-0:/tmp/redis-bootstrap.sh
kubectl --context kind-brokecart -n openbao exec -it openbao-0 -- /bin/sh
```

Inside that shell, read/export the token as above, then:

```sh
sh /tmp/database-credentials.sh
sh /tmp/database-access.sh
sh /tmp/redis-bootstrap.sh
unset BAO_TOKEN
exit
```

The database credential script creates one PostgreSQL administrator credential and 14 separate database/user/password sets. It does **not** create PostgreSQL databases itself. The Argo-managed PostgreSQL provisioning Job creates those databases/users later using the generated credentials.

`database-access.sh` creates:

- `postgres-secrets` role and `postgres-admin-reader` policy for the admin credential.
- `database-provisioner` role and policy for the 14 service database credentials, scoped to `brokecart-postgres`.
- A `<service>-secrets` role and `<service>-db-reader` policy for each service's own namespace/path.

Redis's bootstrap creates one password and two login roles: `redis-secrets` for the server and `cart-redis-secrets` for Cart.

## Bootstrap Kafka, Elasticsearch and application security

From WSL, each launcher prompts privately for the bootstrap token and sends it only through stdin to a temporary authenticated process:

```bash
bash infra/bootstrap/run-kafka-bootstrap.sh
bash infra/bootstrap/run-elasticsearch-bootstrap.sh
bash infra/bootstrap/run-application-security-bootstrap.sh
```

| Path under KV mount `secret` | Content | Consumers |
|---|---|---|
| `brokecart/postgres/admin` | Admin username/password/database | PostgreSQL and database provisioning |
| `brokecart/<service>/database` | That service's DB username/password/name | Service and trusted provisioner |
| `brokecart/redis/auth` | Redis password | Redis and Cart |
| `brokecart/kafka/broker` | Admin credentials and keystore password | Kafka brokers/provisioning |
| `brokecart/<service>/kafka` | SASL username/password | Corresponding application and broker auth configuration |
| `brokecart/kafka-ui/auth` | Kafka UI browser login | Kafka UI |
| `brokecart/kafka-ui/kafka` | Read-only Kafka identity | Kafka UI and Kafka server authentication |
| `brokecart/elasticsearch/admin` | Elasticsearch bootstrap administrator | ES and ES provisioning |
| `brokecart/search/elasticsearch` | Restricted native ES user | Search and ES provisioning |
| `brokecart/identity/jwt` | RSA private/public pair | Identity only |
| `brokecart/shared/jwt` | RSA public key | All HTTP backends |
| `brokecart/shared/internal` | Shared internal token | Backends and maintenance |

The application-security launcher generates a candidate RSA pair in a private temporary directory, preserves an existing valid signing pair, publishes only its public part for other services, and removes temporary key files. Identity gets signing-key read permission; other applications cannot fetch that private-key path. Maintenance gets only the internal token.

Kafka has generated identities for more services than currently use Kafka. Only nine backends enable the Kafka client; ACLs grant only configured event producers/consumers access. A credential existing in OpenBao does not mean every service should mount/use it.

## How ESO fetches one password, step by step

1. Argo creates Catalog's `catalog-secrets` ServiceAccount.
2. SecretStore says use that account, role `catalog-secrets`, audience `vault`, verified OpenBao HTTPS, mount `secret`, version `v2`.
3. ESO uses Kubernetes's TokenRequest API to obtain a short-lived JWT for that account.
4. ESO presents it to OpenBao's Kubernetes login endpoint.
5. OpenBao asks Kubernetes to validate the identity and checks the bound account, namespace and audience.
6. Role policy permits `read` on `secret/data/brokecart/catalog/database`.
7. ESO reads `username`, `password`, `database`, then creates/refreshes Kubernetes Secret `catalog-database-credentials`.
8. Kubelet injects those keys into Catalog's environment. JDBC connects to its own database over verified TLS.

Workload ServiceAccount `catalog` and secret-login ServiceAccount `catalog-secrets` are separate. `automountServiceAccountToken: false` prevents an automatically mounted Pod token; it does not prevent ESO's authorized controller from requesting an explicit token for the login ServiceAccount. Modern ServiceAccounts can legitimately show `SECRETS: 0`.

An application does not need Kubernetes `get secrets` RBAC simply to receive a Secret referenced in its Pod specification. Kubelet performs the configured injection/mount. Giving the workload API permission to list/read all namespace Secrets would be a different, unnecessary privilege here. Platform controllers need explicit API RBAC because they actually watch or reconcile Kubernetes objects.

`creationPolicy: Owner` makes ESO own the generated Kubernetes Secret. The ExternalSecret is a recipe, not the password itself. Never edit the generated Secret expecting the remote credential to change; ESO may overwrite it at the next refresh.

## OpenBao UI through verified upstream HTTPS

The browser connection terminates at Kong, but Kong must use HTTPS again to OpenBao on port 8200. Service annotations in `openbao-values.yaml` select HTTPS, verify the upstream certificate, set the upstream host to its certificate name and reference `brokecart-upstream-ca`.

For the existing CA:

```bash
kubectl --context kind-brokecart apply -f infra/platform/openbao-upstream-ca.yaml
kubectl --context kind-brokecart apply -f infra/platform/openbao-route.yaml
```

For a **new** root CA, first regenerate the public CA ConfigMap manifest instead of applying the old embedded certificate:

```bash
kubectl --context kind-brokecart -n openbao create configmap brokecart-upstream-ca \
  --from-file=ca.crt=/tmp/brokecart-root-ca.crt \
  --from-literal=id="$(python3 -c 'import uuid; print(uuid.uuid4())')" \
  --dry-run=client -o yaml > /tmp/brokecart-upstream-ca.yaml
kubectl --context kind-brokecart apply -f /tmp/brokecart-upstream-ca.yaml
kubectl --context kind-brokecart -n openbao label configmap brokecart-upstream-ca \
  konghq.com/ca-cert=true --overwrite
kubectl --context kind-brokecart -n openbao annotate configmap brokecart-upstream-ca \
  kubernetes.io/ingress.class=kong --overwrite
kubectl --context kind-brokecart apply -f infra/platform/openbao-route.yaml
```

Open `https://openbao.brokecart.com:8443/ui/`. The previous `Client sent an HTTP request to an HTTPS server` error meant Kong used the wrong upstream protocol; changing browser trust did not solve that error. OpenBao browser login is separate from BrokeCart login.

## Verify and rotate deliberately

```bash
kubectl --context kind-brokecart get secretstores -A
kubectl --context kind-brokecart get externalsecrets -A
kubectl --context kind-brokecart -n brokecart-catalog get secret catalog-database-credentials
kubectl --context kind-brokecart -n brokecart-catalog describe secretstore openbao
kubectl --context kind-brokecart -n brokecart-catalog describe externalsecret catalog-database-credentials
```

Healthy states are SecretStore `Valid/True` and ExternalSecret `SecretSynced/True`. Metadata/key counts can be inspected without printing passwords.

Changing an OpenBao password does not automatically change a PostgreSQL role password, Kafka's loaded PLAIN configuration or an existing Elasticsearch bootstrap password. Existing environment variables also do not update inside a running process. Rotation must coordinate provider data, server configuration/native credential change and client Pod restart. Certificate renewal similarly requires verified reload behavior. This repository does not implement an automatic coordinated rotation workflow.

Kubernetes Secret data is base64-encoded, not made confidential merely by base64. RBAC, API/etcd protection, host access and secret handling still matter. Git should contain credential references and public CA material, not actual application credentials.
