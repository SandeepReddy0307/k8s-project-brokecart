# 2. Cluster, networking, Kong and certificates

[Index](README.md) · [Previous](01-architecture.md) · [Next: secrets](03-secrets.md)

## Before touching the cluster

Use WSL Bash with Docker available. Install Git, kind, kubectl, Helm 3, Python 3/PyYAML, OpenSSL and Java 17. Frontend development needs Node.js 22.12 or newer; CI sets up Node.js 22. The Maven wrapper downloads Maven 3.9.11. Check existing tools before installing more copies:

```bash
docker version
kind version
kubectl version --client
helm version --short
python3 --version
python3 -c 'import yaml; print(yaml.__version__)'
openssl version
java -version
free -h
```

Docker must be running. Windows/WSL Docker integration must allow the WSL user to reach its daemon. Three kind nodes do not create more physical RAM. Do not start another full test cluster or the disposable integration test harness alongside this stack on the same laptop.

### Installed platform versions observed on 2026-10-24

| Helm release / namespace | Chart | Chart version | App version shown by Helm |
|---|---|---|---|
| cilium / kube-system | cilium/cilium | 1.20.3 | 1.20.3 |
| metrics-server / kube-system | metrics-server/metrics-server | 3.14.0 | 0.9.0 |
| kong / kong | kong/ingress | 0.24.0 | 3.9; running gateway observed as 3.9.4 |
| cert-manager / cert-manager | jetstack/cert-manager | v1.21.2 | v1.21.2 |
| openbao / openbao | openbao/openbao | 0.30.4 | v2.7.1 |
| external-secrets / external-secrets | external-secrets/external-secrets | 2.13.0 | v2.13.0 |
| monitoring / observability | prometheus-community/kube-prometheus-stack | 92.3.0 | Operator v0.94.1; not the Grafana/Prometheus version |
| loki / observability | grafana-community/loki | 18.16.1 | 3.7.8 |
| fluent-bit / observability | fluent/fluent-bit | 0.58.3 | 5.1.3 |
| tempo / observability | grafana-community/tempo | 3.2.0 | 3.1.0 |
| otel-collector / observability | open-telemetry/opentelemetry-collector | 0.176.0 | 0.162.0 |
| argocd / argocd | argo/argo-cd | 10.10.5 | v3.5.5 |

These are version pins for reproducing this project, not upgrade recommendations. Check current compatibility/security guidance before a future upgrade. A Helm release revision counts installs/upgrades/rollbacks of that release, not application source versions.

## Step 1: kind cluster

`infra/kind/cluster.yaml` defines one control-plane and two worker containers. Only the control-plane has host port mappings:

| Host loopback port | Node container port | Kong Service NodePort | Purpose |
|---|---|---|---|
| 8080 | 30080 | 30080 | HTTP |
| 8443 | 30443 | 30443 | HTTPS |

### Existing cluster

Do not recreate it. Inspect it:

```bash
kind get clusters
kubectl --context kind-brokecart get nodes -o wide
kubectl --context kind-brokecart get storageclass
docker ps --format '{{.Names}} {{.Status}}'
```

### Fresh cluster only: decide CNI before creation

The checked-in kind file does **not** disable kind's default CNI. The observed cluster has both `kindnet` and Cilium DaemonSets. That is an existing configuration caveat, not a clean Cilium-only installation recipe. Do not remove a running CNI blindly: the presence of both DaemonSets alone does not prove which configuration every existing Pod is using.

For a new Cilium-only learning cluster, create a temporary copy with the default CNI disabled, as required by the [Cilium kind guide](https://docs.cilium.io/en/stable/installation/kind/). Preserve the repository's node/port definitions:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
config = yaml.safe_load(Path('infra/kind/cluster.yaml').read_text())
config.setdefault('networking', {})['disableDefaultCNI'] = True
Path('/tmp/brokecart-kind-cilium.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
PY

kind create cluster --name brokecart \
  --image kindest/node:v1.34.0 \
  --config /tmp/brokecart-kind-cilium.yaml
```

This command is for a machine without an existing `brokecart` cluster. With CNI disabled, nodes/CoreDNS may not become Ready until Cilium is installed. Keep kube-proxy because the current Cilium values specify `kubeProxyReplacement: false`.

The kind storage provisioner creates node-local storage using the `standard` StorageClass. `WaitForFirstConsumer` delays provisioning/binding until a consumer can be scheduled. A PVC can therefore legitimately be Pending before a Pod uses it. Its `Delete` reclaim policy means deleting a PVC can delete its data. None of this is a backup or portable network storage.

## Step 2: add Helm repositories

Adding a repository registers a chart index URL on your laptop. It does not install any Pods. Updating the repository downloads index metadata; it does not upgrade a running release.

```bash
helm repo add cilium https://helm.cilium.io/
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo add kong https://charts.konghq.com
helm repo add jetstack https://charts.jetstack.io
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana-community https://grafana-community.github.io/helm-charts
helm repo add fluent https://fluent.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add openbao https://openbao.github.io/openbao-helm
helm repo add external-secrets https://charts.external-secrets.io
helm repo add kafbat https://kafbat.github.io/helm-charts
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
```

Repository names are local aliases. A chart such as `kong/ingress` is looked up using that alias; release name `kong` and namespace `kong` are separate concepts.

## Step 3: Cilium

```bash
helm upgrade --install cilium cilium/cilium \
  --version 1.20.3 --kube-context kind-brokecart \
  --namespace kube-system \
  -f infra/platform/cilium-values.yaml --wait --timeout 10m

kubectl --context kind-brokecart -n kube-system get daemonsets cilium cilium-envoy
kubectl --context kind-brokecart -n kube-system get deployment cilium-operator
kubectl --context kind-brokecart get nodes
```

The values use Kubernetes IPAM, keep kube-proxy and run one Cilium operator. Cilium agents/Envoy are node-level DaemonSets; the operator is a Deployment. Standard Kubernetes NetworkPolicy manifests in our charts describe allowed traffic; Cilium enforces policy where it handles the Pods' networking. There are no Cilium-specific L7 policies or Hubble dashboards provisioned by this repository.

## Step 4: Metrics Server

```bash
helm upgrade --install metrics-server metrics-server/metrics-server \
  --version 3.14.0 --kube-context kind-brokecart \
  --namespace kube-system -f infra/platform/metrics-server-values.yaml \
  --wait --timeout 5m

kubectl --context kind-brokecart get apiservice v1beta1.metrics.k8s.io
kubectl --context kind-brokecart top nodes
```

`--kubelet-insecure-tls` is a local-kind concession: Metrics Server does not validate the kubelet serving certificate. This does not disable the browser, OpenBao or database TLS checks. Metrics Server feeds HPA and `kubectl top`; Prometheus is a different system with retained time-series data.

## Step 5: Gateway API and Kong

Install the API definitions before asking Kubernetes for Gateway resources:

```bash
kubectl --context kind-brokecart apply --server-side \
  -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.3.0/standard-install.yaml

kubectl --context kind-brokecart get crd \
  gatewayclasses.gateway.networking.k8s.io \
  gateways.gateway.networking.k8s.io \
  httproutes.gateway.networking.k8s.io

helm upgrade --install kong kong/ingress \
  --version 0.24.0 --kube-context kind-brokecart \
  --namespace kong --create-namespace \
  -f infra/platform/kong-values.yaml --wait --timeout 10m

kubectl --context kind-brokecart apply -f infra/platform/kong-gateway.yaml
kubectl --context kind-brokecart -n kong get deployment,pods,services
kubectl --context kind-brokecart get gatewayclasses
kubectl --context kind-brokecart -n kong get gateway brokecart-gateway
```

The failed historical `?ref=v3.5` Git kustomize command is not part of this recipe. It referenced a nonexistent Git ref. The installed Kong chart provided its controller-specific CRDs. Inspect `kubectl get crd | rg konghq` after installation rather than assuming any chart upgrade automatically updates all CRDs.

`kong-values.yaml` creates a controller Deployment and gateway Deployment. The controller watches routes and sends configuration to the Admin API; the gateway handles actual browser traffic. `database: off` means DB-less Kong; it does not use our PostgreSQL. Expressions is its router flavor.

The GatewayClass annotation says **unmanaged** because the controller uses an existing Kong data plane instead of provisioning one per Gateway. The data plane itself is still managed by the Helm `kong` release. These two meanings of “managed” are different.

Kong plugins are available concepts, but this repository has no required KongPlugin-based customer authentication configuration. Identity/JWT verification currently lives in the Java applications. Do not claim we installed an OIDC/auth plugin just because Kong supports one.

Kong controller/gateway Deployments belong to the Helm release. `kong-gateway.yaml`, `gateway-certificate.yaml` and the platform UI route files are separately applied platform manifests, not automatically part of that release. Application HTTPRoutes belong to their Argo-managed charts. Resource ownership follows how each object was created, not whether its name contains “kong”.

Backend HTTPRoutes live alongside their target Services. Their `parentRefs` attach to a Gateway in namespace `kong` because its listeners allow routes from all namespaces. This is different from pointing a route's backend at a Service in another namespace, which would need a suitable ReferenceGrant. The current application charts do not author those cross-namespace backend references.

Until an HTTPRoute matches a request, `no Route matched with those values` is expected. A Gateway with no external ADDRESS can still work through our NodePort/host-port mappings.

## Step 6: cert-manager and local signing CA

```bash
helm upgrade --install cert-manager jetstack/cert-manager \
  --version v1.21.2 --kube-context kind-brokecart \
  --namespace cert-manager --create-namespace \
  -f infra/platform/cert-manager-values.yaml --wait --timeout 10m

kubectl --context kind-brokecart apply -f infra/platform/local-ca.yaml
kubectl --context kind-brokecart -n cert-manager \
  wait --for=condition=Ready certificate/brokecart-root-ca --timeout=120s
kubectl --context kind-brokecart \
  wait --for=condition=Ready clusterissuer/brokecart-local-ca --timeout=120s

kubectl --context kind-brokecart apply -f infra/platform/gateway-certificate.yaml
kubectl --context kind-brokecart -n kong \
  wait --for=condition=Ready certificate/brokecart-gateway --timeout=120s
```

cert-manager has three Deployments: controller issues/renews certificates, cainjector distributes CA bundles to supported resources, webhook validates/defaults admission requests. Gateway API support is enabled; our certificates are nevertheless explicitly authored rather than relying on an implicit browser certificate.

`local-ca.yaml` contains three resources:

1. Namespaced self-signed Issuer `brokecart-bootstrap` starts the trust chain.
2. CA Certificate `brokecart-root-ca` generates a long-lived signing keypair in a Secret in `cert-manager`.
3. ClusterIssuer `brokecart-local-ca` uses that CA to sign certificates requested from other namespaces.

`gateway-certificate.yaml` requests a 90-day certificate, renews 15 days before expiry, covers both `brokecart.com` and `*.brokecart.com`, and writes `kong/brokecart-gateway-tls`. The wildcard covers one subdomain level; it does not by itself cover the apex, which is listed separately. `tls.crt` is public; `tls.key` is private. `ca.crt` is public trust data. Leaf rotation does not automatically solve CA replacement or client process reloads.

### Export the public CA, never its private key

```bash
kubectl --context kind-brokecart -n cert-manager \
  get secret brokecart-root-ca -o jsonpath='{.data.tls\.crt}' \
  | base64 --decode > /tmp/brokecart-root-ca.crt

openssl x509 -in /tmp/brokecart-root-ca.crt -noout -subject -issuer -dates
```

For a **fresh CA**, update the public trust copies before activating application charts. Existing checked-in CA files belong to the original local CA and will not trust a newly generated root:

```bash
for chart in application postgres redis kafka kafka-ui elasticsearch maintenance; do
  install -m 644 /tmp/brokecart-root-ca.crt \
    "infra/charts/$chart/files/openbao-ca.crt"
done
```

These files contain public certificates, so they may be committed. Review and commit the change. Never copy the root `tls.key` into Git. The historical filename `openbao-ca.crt` also supplies PostgreSQL trust because the same root signed both servers.

## Step 7: Windows hosts file and browser trust

Edit `C:\Windows\System32\drivers\etc\hosts` as Administrator. Add:

```text
127.0.0.1 brokecart.com grafana.brokecart.com argocd.brokecart.com
127.0.0.1 openbao.brokecart.com kafka.brokecart.com
```

Copy only the public `/tmp/brokecart-root-ca.crt` to a Windows-accessible location. Import it into Windows Trusted Root Certification Authorities for your account and, if your Firefox configuration does not use that trust, into Firefox's Authorities store. Verify the certificate subject/fingerprint before trusting it. A WSL `/etc/hosts` change is not sufficient to configure a Windows browser.

PowerShell connectivity check:

```powershell
Test-NetConnection 127.0.0.1 -Port 8443
```

WSL TLS check before any application route exists:

```bash
curl --noproxy '*' --cacert /tmp/brokecart-root-ca.crt \
  --resolve brokecart.com:8443:127.0.0.1 \
  -i https://brokecart.com:8443/
```

`--resolve` supplies a hostname-to-IP mapping for this request; the hostname is still used for TLS/SNI validation. It does not configure browser DNS. A TLS-verified Kong 404 at this stage proves connectivity/certificate handling, not application routing. Do not use `curl -k` as the normal trust setup.

Proceed to OpenBao/ESO, then observability. Application routes and datastores will later be created by Argo CD, not by manual Helm application installs.
