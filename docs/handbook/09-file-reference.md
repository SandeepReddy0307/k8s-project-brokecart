# 9. File-by-file repository reference

[Index](README.md) · [Previous: operations](08-operations.md)

This reference covers every checked-in infrastructure/platform/bootstrap file and the build/CI/source entry points. Paths link to the actual files. Generated Helm dependency archives, build outputs, credentials and private keys are not source files and do not belong in this inventory.

## Root and build files

| File | Purpose |
|---|---|
| [README.md](../../README.md) | Project entry point, application inventory and handbook link. |
| [pom.xml](../../pom.xml) | Maven parent/reactor; shared dependency versions and Java module build configuration. |
| [mvnw](../../mvnw) | Maven wrapper launcher; downloads/uses the Maven version in wrapper properties. |
| [.mvn/wrapper/maven-wrapper.properties](../../.mvn/wrapper/maven-wrapper.properties) | Pins the Maven distribution URL/version used by the wrapper. |
| [.dockerignore](../../.dockerignore) | Excludes unnecessary host/build/private files from root Docker build context. |
| [.gitignore](../../.gitignore) | Keeps build outputs, downloaded chart packages and local/private artifacts out of source control. |
| [.github/actionlint.yaml](../../.github/actionlint.yaml) | Recognizes the custom brokecart self-hosted runner label for workflow validation. |

## kind and platform values/manifests

| File | Purpose |
|---|---|
| [infra/kind/cluster.yaml](../../infra/kind/cluster.yaml) | Three kind nodes and host-loopback NodePort mappings. Does not disable kindnet; see the fresh Cilium-only overlay in chapter 2. |
| [infra/platform/argocd-route.yaml](../../infra/platform/argocd-route.yaml) | Argo CD subdomain HTTPRoute to argocd-server port 80. |
| [infra/platform/argocd-values.yaml](../../infra/platform/argocd-values.yaml) | Argo URL/internal HTTP, child/ESO/Certificate health Lua and bounded controller memory/concurrency. |
| [infra/platform/cert-manager-values.yaml](../../infra/platform/cert-manager-values.yaml) | Install certificate CRDs and enable Gateway API support. |
| [infra/platform/cilium-values.yaml](../../infra/platform/cilium-values.yaml) | Kubernetes IPAM, kube-proxy retained, one operator; Cilium platform Helm inputs. |
| [infra/platform/external-secrets-values.yaml](../../infra/platform/external-secrets-values.yaml) | ESO main controller, webhook and cert controller replicas/resources/CRDs. |
| [infra/platform/fluent-bit-values.yaml](../../infra/platform/fluent-bit-values.yaml) | DaemonSet node log mounts, CRI tail input, Kubernetes enrichment, Loki output and buffering. |
| [infra/platform/gateway-certificate.yaml](../../infra/platform/gateway-certificate.yaml) | Apex/wildcard browser certificate and kong namespace TLS Secret target. |
| [infra/platform/grafana-route.yaml](../../infra/platform/grafana-route.yaml) | Grafana subdomain HTTPRoute to monitoring-grafana Service port 80. |
| [infra/platform/kong-gateway.yaml](../../infra/platform/kong-gateway.yaml) | GatewayClass kong and shared HTTP/HTTPS Gateway with cross-namespace route attachment. |
| [infra/platform/kong-values.yaml](../../infra/platform/kong-values.yaml) | Kong controller/gateway release, DB-less expression router and NodePorts 30080/30443. |
| [infra/platform/local-ca.yaml](../../infra/platform/local-ca.yaml) | Self-signed bootstrap Issuer, long-lived local root Certificate and CA ClusterIssuer. |
| [infra/platform/loki-values.yaml](../../infra/platform/loki-values.yaml) | Monolithic Loki, filesystem/TSDB storage, retention, gateway and disabled optional components. |
| [infra/platform/metrics-server-values.yaml](../../infra/platform/metrics-server-values.yaml) | One resource-metrics server and local kubelet TLS verification concession. |
| [infra/platform/monitoring-values.yaml](../../infra/platform/monitoring-values.yaml) | Prometheus Operator stack, Prometheus/Grafana/Alertmanager storage and resource settings. |
| [infra/platform/openbao-route.yaml](../../infra/platform/openbao-route.yaml) | OpenBao subdomain route; preserves /ui/ and uses the OpenBao UI Service. |
| [infra/platform/openbao-upstream-ca.yaml](../../infra/platform/openbao-upstream-ca.yaml) | Public CA ConfigMap labelled for Kong upstream certificate verification; regenerate for a fresh CA. |
| [infra/platform/openbao-values.yaml](../../infra/platform/openbao-values.yaml) | Persistent TLS Raft OpenBao server, UI Service HTTPS upstream annotations and server Certificate. |
| [infra/platform/otel-collector-values.yaml](../../infra/platform/otel-collector-values.yaml) | Trace-only OTLP receiver, memory limiter, batch processor and retrying Tempo exporter. |
| [infra/platform/tempo-values.yaml](../../infra/platform/tempo-values.yaml) | Single persistent Tempo, local trace storage/retention, OTLP receivers, query/memory budget. |

## Bootstrap scripts

Run WSL launchers from the repository root. Other scripts run inside an authenticated OpenBao shell as described in chapter 3. These write credentials/policies in OpenBao; they do not deploy application Pods.

| File | Purpose |
|---|---|
| [application-security-access.sh](../../infra/bootstrap/application-security-access.sh) | Identity-only private-key policy, shared public-key/token policies and maintenance token-only role. |
| [application-security-credentials.sh](../../infra/bootstrap/application-security-credentials.sh) | Preserve/create RSA signing/public-key paths and shared internal token, with consistency checks. |
| [database-access.sh](../../infra/bootstrap/database-access.sh) | Scoped admin, database-provisioner and per-service OpenBao policies/Kubernetes auth roles. |
| [database-credentials.sh](../../infra/bootstrap/database-credentials.sh) | Create/preserve admin plus 14 database username/password/name paths; random hex passwords and create-only CAS. |
| [elasticsearch-access.sh](../../infra/bootstrap/elasticsearch-access.sh) | Bind ES server/Search credential reads to exact service accounts and namespaces. |
| [elasticsearch-credentials.sh](../../infra/bootstrap/elasticsearch-credentials.sh) | Create/preserve elastic bootstrap and restricted Search credentials. |
| [kafka-access.sh](../../infra/bootstrap/kafka-access.sh) | Assign Kafka server, application-client and UI credential policies to exact accounts/namespaces. |
| [kafka-credentials.sh](../../infra/bootstrap/kafka-credentials.sh) | Create/preserve Kafka broker/admin/keystore and per-client/UI credentials. |
| [redis-bootstrap.sh](../../infra/bootstrap/redis-bootstrap.sh) | Create/preserve Redis password and server/Cart read roles. |
| [run-application-security-bootstrap.sh](../../infra/bootstrap/run-application-security-bootstrap.sh) | Generate a protected candidate RSA pair, stream it privately, preserve existing keys and remove temporary files. |
| [run-elasticsearch-bootstrap.sh](../../infra/bootstrap/run-elasticsearch-bootstrap.sh) | WSL hidden-token launcher for Elasticsearch credential/access scripts. |
| [run-kafka-bootstrap.sh](../../infra/bootstrap/run-kafka-bootstrap.sh) | WSL hidden-token launcher; streams Kafka scripts into a temporary OpenBao process. |

## Every chart file

Charts use a shared naming vocabulary, but objects are evaluated in each release namespace. A template with multiple YAML documents can create several resource types. Some templates render only when a dependency/feature is enabled.

### application

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/application/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/openbao-ca.crt](../../infra/charts/application/files/openbao-ca.crt) | Public local root CA; regenerate trust copies when creating a new root. Not a private key. |
| [templates/_validation.tpl](../../infra/charts/application/templates/_validation.tpl) | Helm input validation helpers; rejects incompatible/missing settings before applying any object. |
| [templates/configmap.yaml](../../infra/charts/application/templates/configmap.yaml) | Public runtime configuration. For PostgreSQL/Redis/Kafka/ES charts, contains that server configuration; for application, renders environment settings. |
| [templates/database-ca.yaml](../../infra/charts/application/templates/database-ca.yaml) | Public PostgreSQL client CA ConfigMap mounted by Java backends. |
| [templates/deployment.yaml](../../infra/charts/application/templates/deployment.yaml) | Backend Deployment, probes, config checksums, Secret environment references, resources, security, conditional Search trust init container and volumes. |
| [templates/elasticsearch-credentials.yaml](../../infra/charts/application/templates/elasticsearch-credentials.yaml) | Conditional ES login ServiceAccount, verified SecretStore and Search credential ExternalSecret. |
| [templates/externalsecret.yaml](../../infra/charts/application/templates/externalsecret.yaml) | ESO instruction to fetch the server/application credential keys from the configured remote path. |
| [templates/hpa.yaml](../../infra/charts/application/templates/hpa.yaml) | CPU HPA attached to the backend Deployment, with bounded scale-up/down behavior. |
| [templates/httproute.yaml](../../infra/charts/application/templates/httproute.yaml) | Configured public backend API prefixes on shared Kong HTTPS Gateway; absent for internal-only provider. |
| [templates/kafka-configmap.yaml](../../infra/charts/application/templates/kafka-configmap.yaml) | Conditional public Kafka CA and Spring client configuration for SASL_SSL/PLAIN. |
| [templates/kafka-externalsecret.yaml](../../infra/charts/application/templates/kafka-externalsecret.yaml) | Fetch Kafka username/password and build an escaped JAAS configuration Secret value. |
| [templates/kafka-secretstore.yaml](../../infra/charts/application/templates/kafka-secretstore.yaml) | Verified OpenBao provider login for this backend Kafka identity. |
| [templates/kafka-serviceaccount.yaml](../../infra/charts/application/templates/kafka-serviceaccount.yaml) | Explicit ServiceAccount ESO uses for Kafka credential login. |
| [templates/networkpolicy.yaml](../../infra/charts/application/templates/networkpolicy.yaml) | Chart-specific selected ingress/egress rules; read namespace/port selectors to see the actual boundary. |
| [templates/pdb.yaml](../../infra/charts/application/templates/pdb.yaml) | Disruption budget: Kafka minAvailable two or backend maxUnavailable one. |
| [templates/redis-credentials.yaml](../../infra/charts/application/templates/redis-credentials.yaml) | Conditional Cart Redis credential ServiceAccount, SecretStore and ExternalSecret. |
| [templates/secret-serviceaccount.yaml](../../infra/charts/application/templates/secret-serviceaccount.yaml) | Explicit ESO provider-login identity with automatic token mounting disabled. |
| [templates/secretstore.yaml](../../infra/charts/application/templates/secretstore.yaml) | Verified OpenBao server/CA, KV v2 mount and Kubernetes role/account/audience selection. |
| [templates/security-externalsecret.yaml](../../infra/charts/application/templates/security-externalsecret.yaml) | Shared internal token/public JWT, plus private JWT key only for Identity. |
| [templates/security-secretstore.yaml](../../infra/charts/application/templates/security-secretstore.yaml) | Provider connection using this service application-security role/account. |
| [templates/security-serviceaccount.yaml](../../infra/charts/application/templates/security-serviceaccount.yaml) | Identity for ESO application-security credential retrieval. |
| [templates/service.yaml](../../infra/charts/application/templates/service.yaml) | Backend stable ClusterIP Service mapping port 80 to named container HTTP port. |
| [templates/serviceaccount.yaml](../../infra/charts/application/templates/serviceaccount.yaml) | Application/server workload identity; automatic token mounting disabled in our custom workloads. |
| [templates/servicemonitor.yaml](../../infra/charts/application/templates/servicemonitor.yaml) | Monitoring release selector, service labels, named port, metrics path and 60s backend scrape interval. |
| [templates/vpa.yaml](../../infra/charts/application/templates/vpa.yaml) | Optional disabled recommendation-only VPA; requires separately installed controller/CRDs. |
| [values.yaml](../../infra/charts/application/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### elasticsearch

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/elasticsearch/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/check-ready.sh](../../infra/charts/elasticsearch/files/check-ready.sh) | Authenticated verified HTTPS loopback ES probe; avoids ready-Service circular dependency. |
| [files/openbao-ca.crt](../../infra/charts/elasticsearch/files/openbao-ca.crt) | Public local root CA; regenerate trust copies when creating a new root. Not a private key. |
| [files/prepare-config.sh](../../infra/charts/elasticsearch/files/prepare-config.sh) | Copy ES image configuration into a writable config volume before read-only main startup. |
| [files/product-index.json](../../infra/charts/elasticsearch/files/product-index.json) | Elasticsearch product-index mapping/settings, one primary and zero replicas. |
| [files/provision.sh](../../infra/charts/elasticsearch/files/provision.sh) | Idempotent ES role/user/index setup with private temporary authentication files. |
| [files/search-role.json](../../infra/charts/elasticsearch/files/search-role.json) | ES permissions limited to brokecart-products, with no cluster/security administration. |
| [files/start.sh](../../infra/charts/elasticsearch/files/start.sh) | ES startup adapter reading mounted admin password and invoking the image entrypoint. |
| [templates/certificate.yaml](../../infra/charts/elasticsearch/templates/certificate.yaml) | cert-manager leaf Certificate for the server DNS names and local signing ClusterIssuer. |
| [templates/configmap.yaml](../../infra/charts/elasticsearch/templates/configmap.yaml) | Public runtime configuration. For PostgreSQL/Redis/Kafka/ES charts, contains that server configuration; for application, renders environment settings. |
| [templates/externalsecrets.yaml](../../infra/charts/elasticsearch/templates/externalsecrets.yaml) | ES admin and restricted Search credential fetch instructions. |
| [templates/networkpolicy.yaml](../../infra/charts/elasticsearch/templates/networkpolicy.yaml) | Chart-specific selected ingress/egress rules; read namespace/port selectors to see the actual boundary. |
| [templates/provisioning-job.yaml](../../infra/charts/elasticsearch/templates/provisioning-job.yaml) | Finite Sync hook: PostgreSQL roles/databases or ES restricted user/index provisioning, with mounted credentials and verified TLS. |
| [templates/secret-serviceaccount.yaml](../../infra/charts/elasticsearch/templates/secret-serviceaccount.yaml) | Explicit ESO provider-login identity with automatic token mounting disabled. |
| [templates/secretstore.yaml](../../infra/charts/elasticsearch/templates/secretstore.yaml) | Verified OpenBao server/CA, KV v2 mount and Kubernetes role/account/audience selection. |
| [templates/serviceaccount.yaml](../../infra/charts/elasticsearch/templates/serviceaccount.yaml) | Application/server workload identity; automatic token mounting disabled in our custom workloads. |
| [templates/services.yaml](../../infra/charts/elasticsearch/templates/services.yaml) | Regular ClusterIP Service plus StatefulSet headless discovery Service. |
| [templates/statefulset.yaml](../../infra/charts/elasticsearch/templates/statefulset.yaml) | Stable named server Pods, PVC templates, resources/security/probes and server-specific TLS/data mounts. |
| [values.yaml](../../infra/charts/elasticsearch/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### frontend

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/frontend/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [templates/networkpolicy.yaml](../../infra/charts/frontend/templates/networkpolicy.yaml) | Chart-specific selected ingress/egress rules; read namespace/port selectors to see the actual boundary. |
| [templates/route.yaml](../../infra/charts/frontend/templates/route.yaml) | Frontend or Kafka UI host/path route to that chart Service. |
| [templates/scaling.yaml](../../infra/charts/frontend/templates/scaling.yaml) | Optional frontend HPA/PDB manifests; baseline disabled and bounds one. |
| [templates/workload.yaml](../../infra/charts/frontend/templates/workload.yaml) | Frontend ServiceAccount, Service and non-root Nginx Deployment with probes/writable temp space. |
| [values.yaml](../../infra/charts/frontend/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### kafka

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/kafka/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/admin-client.sh](../../infra/charts/kafka/files/admin-client.sh) | Kafka administrative client config helper; reads mounted credentials and writes a private temporary file. |
| [files/openbao-ca.crt](../../infra/charts/kafka/files/openbao-ca.crt) | Public local root CA; regenerate trust copies when creating a new root. Not a private key. |
| [files/start-kafka.sh](../../infra/charts/kafka/files/start-kafka.sh) | Validate broker identity, assemble private server auth configuration, format new storage and start Kafka. |
| [templates/_validation.tpl](../../infra/charts/kafka/templates/_validation.tpl) | Helm input validation helpers; rejects incompatible/missing settings before applying any object. |
| [templates/certificate.yaml](../../infra/charts/kafka/templates/certificate.yaml) | cert-manager leaf Certificate for the server DNS names and local signing ClusterIssuer. |
| [templates/client-externalsecrets.yaml](../../infra/charts/kafka/templates/client-externalsecrets.yaml) | Fetch configured Kafka client credentials for broker authentication configuration. |
| [templates/configmap.yaml](../../infra/charts/kafka/templates/configmap.yaml) | Public runtime configuration. For PostgreSQL/Redis/Kafka/ES charts, contains that server configuration; for application, renders environment settings. |
| [templates/externalsecret.yaml](../../infra/charts/kafka/templates/externalsecret.yaml) | ESO instruction to fetch the server/application credential keys from the configured remote path. |
| [templates/networkpolicy.yaml](../../infra/charts/kafka/templates/networkpolicy.yaml) | Chart-specific selected ingress/egress rules; read namespace/port selectors to see the actual boundary. |
| [templates/pdb.yaml](../../infra/charts/kafka/templates/pdb.yaml) | Disruption budget: Kafka minAvailable two or backend maxUnavailable one. |
| [templates/secret-serviceaccount.yaml](../../infra/charts/kafka/templates/secret-serviceaccount.yaml) | Explicit ESO provider-login identity with automatic token mounting disabled. |
| [templates/secretstore.yaml](../../infra/charts/kafka/templates/secretstore.yaml) | Verified OpenBao server/CA, KV v2 mount and Kubernetes role/account/audience selection. |
| [templates/serviceaccount.yaml](../../infra/charts/kafka/templates/serviceaccount.yaml) | Application/server workload identity; automatic token mounting disabled in our custom workloads. |
| [templates/services.yaml](../../infra/charts/kafka/templates/services.yaml) | Regular ClusterIP Service plus StatefulSet headless discovery Service. |
| [templates/startup-configmap.yaml](../../infra/charts/kafka/templates/startup-configmap.yaml) | Packages the Kafka startup script as public ConfigMap text. |
| [templates/statefulset.yaml](../../infra/charts/kafka/templates/statefulset.yaml) | Stable named server Pods, PVC templates, resources/security/probes and server-specific TLS/data mounts. |
| [templates/topics-configmap.yaml](../../infra/charts/kafka/templates/topics-configmap.yaml) | Packages admin helper and generated create-topic/ACL scripts from values. |
| [templates/topics-job.yaml](../../infra/charts/kafka/templates/topics-job.yaml) | Kafka Sync hook waits for API, creates topics and applies ACLs; successful hook is cleaned up. |
| [values.yaml](../../infra/charts/kafka/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### kafka-ui

| File | Purpose |
|---|---|
| [Chart.lock](../../infra/charts/kafka-ui/Chart.lock) | Dependency resolution lock for the pinned upstream Kafka UI chart. |
| [Chart.yaml](../../infra/charts/kafka-ui/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/openbao-ca.crt](../../infra/charts/kafka-ui/files/openbao-ca.crt) | Public local root CA; regenerate trust copies when creating a new root. Not a private key. |
| [templates/ca-configmap.yaml](../../infra/charts/kafka-ui/templates/ca-configmap.yaml) | Public CA mounted by the Kafka UI client. |
| [templates/client-externalsecret.yaml](../../infra/charts/kafka-ui/templates/client-externalsecret.yaml) | Kafka UI broker-client credential/JAAS value, separate from browser login. |
| [templates/route.yaml](../../infra/charts/kafka-ui/templates/route.yaml) | Frontend or Kafka UI host/path route to that chart Service. |
| [templates/secret-serviceaccount.yaml](../../infra/charts/kafka-ui/templates/secret-serviceaccount.yaml) | Explicit ESO provider-login identity with automatic token mounting disabled. |
| [templates/secretstore.yaml](../../infra/charts/kafka-ui/templates/secretstore.yaml) | Verified OpenBao server/CA, KV v2 mount and Kubernetes role/account/audience selection. |
| [templates/serviceaccount.yaml](../../infra/charts/kafka-ui/templates/serviceaccount.yaml) | Application/server workload identity; automatic token mounting disabled in our custom workloads. |
| [templates/ui-externalsecret.yaml](../../infra/charts/kafka-ui/templates/ui-externalsecret.yaml) | Kafka UI browser login username/password delivery. |
| [values.yaml](../../infra/charts/kafka-ui/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### maintenance

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/maintenance/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/openbao-ca.crt](../../infra/charts/maintenance/files/openbao-ca.crt) | Public local root CA; regenerate trust copies when creating a new root. Not a private key. |
| [templates/cronjobs.yaml](../../infra/charts/maintenance/templates/cronjobs.yaml) | Two finite maintenance task schedules/Jobs, initially suspended, no inbound Service. |
| [templates/networkpolicy.yaml](../../infra/charts/maintenance/templates/networkpolicy.yaml) | Chart-specific selected ingress/egress rules; read namespace/port selectors to see the actual boundary. |
| [templates/secrets.yaml](../../infra/charts/maintenance/templates/secrets.yaml) | Maintenance workload/login identities, scoped token-only provider store and ExternalSecret. |
| [values.yaml](../../infra/charts/maintenance/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### observability-config

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/observability-config/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/brokecart-overview.json](../../infra/charts/observability-config/files/brokecart-overview.json) | Grafana dashboard panels, variables and PromQL/LogQL/TraceQL queries. |
| [templates/alerts.yaml](../../infra/charts/observability-config/templates/alerts.yaml) | PrometheusRule containing four application/workload alerts. |
| [templates/dashboards.yaml](../../infra/charts/observability-config/templates/dashboards.yaml) | Grafana-discoverable dashboard ConfigMap from packaged JSON. |
| [values.yaml](../../infra/charts/observability-config/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### postgres

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/postgres/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/openbao-ca.crt](../../infra/charts/postgres/files/openbao-ca.crt) | Public local root CA; regenerate trust copies when creating a new root. Not a private key. |
| [templates/certificate.yaml](../../infra/charts/postgres/templates/certificate.yaml) | cert-manager leaf Certificate for the server DNS names and local signing ClusterIssuer. |
| [templates/externalsecret.yaml](../../infra/charts/postgres/templates/externalsecret.yaml) | ESO instruction to fetch the server/application credential keys from the configured remote path. |
| [templates/networkpolicy.yaml](../../infra/charts/postgres/templates/networkpolicy.yaml) | Chart-specific selected ingress/egress rules; read namespace/port selectors to see the actual boundary. |
| [templates/provisioning-configmap.yaml](../../infra/charts/postgres/templates/provisioning-configmap.yaml) | PostgreSQL public shell/SQL provisioner; values come from mounted credentials, not password literals in SQL source. |
| [templates/provisioning-externalsecrets.yaml](../../infra/charts/postgres/templates/provisioning-externalsecrets.yaml) | Copy each service database credential into PostgreSQL namespace for trusted provisioning. |
| [templates/provisioning-job.yaml](../../infra/charts/postgres/templates/provisioning-job.yaml) | Finite Sync hook: PostgreSQL roles/databases or ES restricted user/index provisioning, with mounted credentials and verified TLS. |
| [templates/provisioning-secretstore.yaml](../../infra/charts/postgres/templates/provisioning-secretstore.yaml) | Separate OpenBao login restricted to the managed service database credential paths. |
| [templates/provisioning-serviceaccount.yaml](../../infra/charts/postgres/templates/provisioning-serviceaccount.yaml) | ESO login identity for the database-provisioner role. |
| [templates/secret-serviceaccount.yaml](../../infra/charts/postgres/templates/secret-serviceaccount.yaml) | Explicit ESO provider-login identity with automatic token mounting disabled. |
| [templates/secretstore.yaml](../../infra/charts/postgres/templates/secretstore.yaml) | Verified OpenBao server/CA, KV v2 mount and Kubernetes role/account/audience selection. |
| [templates/serviceaccount.yaml](../../infra/charts/postgres/templates/serviceaccount.yaml) | Application/server workload identity; automatic token mounting disabled in our custom workloads. |
| [templates/services.yaml](../../infra/charts/postgres/templates/services.yaml) | Regular ClusterIP Service plus StatefulSet headless discovery Service. |
| [templates/statefulset.yaml](../../infra/charts/postgres/templates/statefulset.yaml) | Stable named server Pods, PVC templates, resources/security/probes and server-specific TLS/data mounts. |
| [values.yaml](../../infra/charts/postgres/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |
### redis

| File | Purpose |
|---|---|
| [Chart.yaml](../../infra/charts/redis/Chart.yaml) | Chart metadata, semantic chart version and any pinned dependencies; application version is separate. |
| [files/openbao-ca.crt](../../infra/charts/redis/files/openbao-ca.crt) | Public local root CA; regenerate trust copies when creating a new root. Not a private key. |
| [templates/configmap.yaml](../../infra/charts/redis/templates/configmap.yaml) | Public runtime configuration. For PostgreSQL/Redis/Kafka/ES charts, contains that server configuration; for application, renders environment settings. |
| [templates/externalsecret.yaml](../../infra/charts/redis/templates/externalsecret.yaml) | ESO instruction to fetch the server/application credential keys from the configured remote path. |
| [templates/networkpolicy.yaml](../../infra/charts/redis/templates/networkpolicy.yaml) | Chart-specific selected ingress/egress rules; read namespace/port selectors to see the actual boundary. |
| [templates/secret-serviceaccount.yaml](../../infra/charts/redis/templates/secret-serviceaccount.yaml) | Explicit ESO provider-login identity with automatic token mounting disabled. |
| [templates/secretstore.yaml](../../infra/charts/redis/templates/secretstore.yaml) | Verified OpenBao server/CA, KV v2 mount and Kubernetes role/account/audience selection. |
| [templates/serviceaccount.yaml](../../infra/charts/redis/templates/serviceaccount.yaml) | Application/server workload identity; automatic token mounting disabled in our custom workloads. |
| [templates/services.yaml](../../infra/charts/redis/templates/services.yaml) | Regular ClusterIP Service plus StatefulSet headless discovery Service. |
| [templates/statefulset.yaml](../../infra/charts/redis/templates/statefulset.yaml) | Stable named server Pods, PVC templates, resources/security/probes and server-specific TLS/data mounts. |
| [values.yaml](../../infra/charts/redis/values.yaml) | Default chart inputs; application/frontend/maintenance can also receive infra/values release overrides. |

## Argo CD and per-release values

| File | Purpose |
|---|---|
| [infra/argocd/applications/cart.yaml](../../infra/argocd/applications/cart.yaml) | Child Application cart; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/catalog.yaml](../../infra/argocd/applications/catalog.yaml) | Child Application catalog; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/checkout.yaml](../../infra/argocd/applications/checkout.yaml) | Child Application checkout; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/elasticsearch.yaml](../../infra/argocd/applications/elasticsearch.yaml) | Child Application elasticsearch; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/frontend.yaml](../../infra/argocd/applications/frontend.yaml) | Child Application frontend; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/identity.yaml](../../infra/argocd/applications/identity.yaml) | Child Application identity; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/inventory.yaml](../../infra/argocd/applications/inventory.yaml) | Child Application inventory; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/kafka-ui.yaml](../../infra/argocd/applications/kafka-ui.yaml) | Child Application kafka-ui; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/kafka.yaml](../../infra/argocd/applications/kafka.yaml) | Child Application kafka; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/maintenance.yaml](../../infra/argocd/applications/maintenance.yaml) | Child Application maintenance; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/notifications.yaml](../../infra/argocd/applications/notifications.yaml) | Child Application notifications; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/observability-config.yaml](../../infra/argocd/applications/observability-config.yaml) | Child Application observability-config; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/orders.yaml](../../infra/argocd/applications/orders.yaml) | Child Application orders; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/payment-provider.yaml](../../infra/argocd/applications/payment-provider.yaml) | Child Application payment-provider; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/payments.yaml](../../infra/argocd/applications/payments.yaml) | Child Application payments; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/postgres.yaml](../../infra/argocd/applications/postgres.yaml) | Child Application postgres; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/pricing.yaml](../../infra/argocd/applications/pricing.yaml) | Child Application pricing; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/redis.yaml](../../infra/argocd/applications/redis.yaml) | Child Application redis; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/reporting.yaml](../../infra/argocd/applications/reporting.yaml) | Child Application reporting; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/returns.yaml](../../infra/argocd/applications/returns.yaml) | Child Application returns; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/search.yaml](../../infra/argocd/applications/search.yaml) | Child Application search; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/applications/shipping.yaml](../../infra/argocd/applications/shipping.yaml) | Child Application shipping; chart/value source, target namespace, parent sync wave and sync policy. |
| [infra/argocd/root-application.yaml](../../infra/argocd/root-application.yaml) | Parent app-of-apps; watches the child Application directory on main, automatic prune/self-heal and retries. |
| [infra/values/cart.yaml](../../infra/values/cart.yaml) | cart release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/catalog.yaml](../../infra/values/catalog.yaml) | catalog release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/checkout.yaml](../../infra/values/checkout.yaml) | checkout release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/frontend.yaml](../../infra/values/frontend.yaml) | frontend release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/identity.yaml](../../infra/values/identity.yaml) | identity release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/inventory.yaml](../../infra/values/inventory.yaml) | inventory release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/maintenance.yaml](../../infra/values/maintenance.yaml) | maintenance release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/notifications.yaml](../../infra/values/notifications.yaml) | notifications release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/orders.yaml](../../infra/values/orders.yaml) | orders release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/payment-provider.yaml](../../infra/values/payment-provider.yaml) | payment-provider release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/payments.yaml](../../infra/values/payments.yaml) | payments release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/pricing.yaml](../../infra/values/pricing.yaml) | pricing release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/reporting.yaml](../../infra/values/reporting.yaml) | reporting release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/returns.yaml](../../infra/values/returns.yaml) | returns release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/search.yaml](../../infra/values/search.yaml) | search release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |
| [infra/values/shipping.yaml](../../infra/values/shipping.yaml) | shipping release overrides: actual image repository/SHA and service-specific settings; CI promotes image fields here. |

## CI and validation files

| File | Purpose |
|---|---|
| [.github/workflows/build-images.yaml](../../.github/workflows/build-images.yaml) | Changed-service detection, reusable build matrix and tested-image GitOps promotion. |
| [.github/workflows/service-build.yaml](../../.github/workflows/service-build.yaml) | One selected Maven/frontend test and image build/push using Environment credentials. |
| [.github/workflows/validate-infrastructure.yaml](../../.github/workflows/validate-infrastructure.yaml) | Pinned actionlint plus infrastructure/configuration tests; no live deployment. |
| [scripts/ci/check_promotion.py](../../scripts/ci/check_promotion.py) | Rejects stale image promotions when newer source changes affect selected services. |
| [scripts/ci/check_workflows.py](../../scripts/ci/check_workflows.py) | Downloads/verifies pinned actionlint or uses an explicit binary to validate workflow syntax. |
| [scripts/ci/select_services.py](../../scripts/ci/select_services.py) | Maps Git diff/manual allowlisted service selection to build matrix entries. |
| [scripts/ci/update_images.py](../../scripts/ci/update_images.py) | Updates only selected image repository/tag fields in release values. |
| [scripts/ci/validate_infra.py](../../scripts/ci/validate_infra.py) | Restores optional chart dependencies, lints/renders charts and validates references. |
| [scripts/preflight.py](../../scripts/preflight.py) | Checks image/config readiness and optional read-only live platform requirements. |

Configuration test files under `tests/*configuration.py` validate the corresponding charts/security/routing/CI contracts. `tests/ci_configuration.py` checks changed-service selection/promotion behavior using temporary Git fixtures. Runtime tests such as `commerce_flow.py`, `browser_flow.py`, `real_dependencies.py`, `kafka_runtime.py` and `elasticsearch_runtime.py` have different runtime/container requirements; read them before running beside the local cluster.

## Source files by service

Each service section links its complete source/build directory. Read controller mapping/transaction annotations together with the shared security/event code; a single controller method does not describe the entire distributed operation.

### cart-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/cart-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/cart-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/cart/CartApplication.java](../../services/cart-service/src/main/java/com/brokecart/cart/CartApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/cart/CartController.java](../../services/cart-service/src/main/java/com/brokecart/cart/CartController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/cart-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/cart-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### catalog-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/catalog-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/catalog-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/catalog/CatalogApplication.java](../../services/catalog-service/src/main/java/com/brokecart/catalog/CatalogApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/catalog/CatalogController.java](../../services/catalog-service/src/main/java/com/brokecart/catalog/CatalogController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/java/com/brokecart/catalog/CatalogOperations.java](../../services/catalog-service/src/main/java/com/brokecart/catalog/CatalogOperations.java) | Operator-only domain mutation and associated event publication. |
| [src/main/java/com/brokecart/catalog/Product.java](../../services/catalog-service/src/main/java/com/brokecart/catalog/Product.java) | Domain/model/configuration logic used by this module; follow references from its controller/entry point. |
| [src/main/java/com/brokecart/catalog/ProductRepository.java](../../services/catalog-service/src/main/java/com/brokecart/catalog/ProductRepository.java) | Persistence access interface used by this domain. |
| [src/main/resources/application-local.yaml](../../services/catalog-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/catalog-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/db/migration/V1__catalog.sql](../../services/catalog-service/src/main/resources/db/migration/V1__catalog.sql) | Versioned Flyway schema/seed migration; changing history requires a migration strategy. |
| [src/test/java/com/brokecart/catalog/CatalogApiTest.java](../../services/catalog-service/src/test/java/com/brokecart/catalog/CatalogApiTest.java) | Application unit/contract test; not proof of the deployed Kubernetes journey. |
### checkout-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/checkout-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/checkout-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/checkout/CheckoutApplication.java](../../services/checkout-service/src/main/java/com/brokecart/checkout/CheckoutApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/checkout/CheckoutController.java](../../services/checkout-service/src/main/java/com/brokecart/checkout/CheckoutController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/checkout-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/checkout-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### identity-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/identity-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/identity-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/identity/IdentityApplication.java](../../services/identity-service/src/main/java/com/brokecart/identity/IdentityApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/identity/IdentityController.java](../../services/identity-service/src/main/java/com/brokecart/identity/IdentityController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/identity-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/identity-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### inventory-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/inventory-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/inventory-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/inventory/InventoryApplication.java](../../services/inventory-service/src/main/java/com/brokecart/inventory/InventoryApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/inventory/InventoryController.java](../../services/inventory-service/src/main/java/com/brokecart/inventory/InventoryController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/java/com/brokecart/inventory/ReservationExpiry.java](../../services/inventory-service/src/main/java/com/brokecart/inventory/ReservationExpiry.java) | Reservation expiry API and safe coordination with order lifecycle. |
| [src/main/resources/application-local.yaml](../../services/inventory-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/inventory-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### maintenance-worker

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/maintenance-worker/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/maintenance-worker/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/maintenance/MaintenanceWorker.java](../../services/maintenance-worker/src/main/java/com/brokecart/maintenance/MaintenanceWorker.java) | Domain/model/configuration logic used by this module; follow references from its controller/entry point. |
### notifications-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/notifications-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/notifications-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/notifications/NotificationsApplication.java](../../services/notifications-service/src/main/java/com/brokecart/notifications/NotificationsApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/notifications/NotificationsController.java](../../services/notifications-service/src/main/java/com/brokecart/notifications/NotificationsController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/notifications-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/notifications-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### orders-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/orders-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/orders-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/orders/OrdersApplication.java](../../services/orders-service/src/main/java/com/brokecart/orders/OrdersApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/orders/OrdersController.java](../../services/orders-service/src/main/java/com/brokecart/orders/OrdersController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/orders-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/orders-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### payment-provider-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/payment-provider-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/payment-provider-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/paymentprovider/PaymentProviderApplication.java](../../services/payment-provider-service/src/main/java/com/brokecart/paymentprovider/PaymentProviderApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/paymentprovider/ProviderController.java](../../services/payment-provider-service/src/main/java/com/brokecart/paymentprovider/ProviderController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/payment-provider-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/payment-provider-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### payments-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/payments-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/payments-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/payments/PaymentsApplication.java](../../services/payments-service/src/main/java/com/brokecart/payments/PaymentsApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/payments/PaymentsController.java](../../services/payments-service/src/main/java/com/brokecart/payments/PaymentsController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/payments-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/payments-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### pricing-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/pricing-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/pricing-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/pricing/CatalogClient.java](../../services/pricing-service/src/main/java/com/brokecart/pricing/CatalogClient.java) | Domain/model/configuration logic used by this module; follow references from its controller/entry point. |
| [src/main/java/com/brokecart/pricing/PricingApplication.java](../../services/pricing-service/src/main/java/com/brokecart/pricing/PricingApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/pricing/PricingController.java](../../services/pricing-service/src/main/java/com/brokecart/pricing/PricingController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/java/com/brokecart/pricing/QuoteService.java](../../services/pricing-service/src/main/java/com/brokecart/pricing/QuoteService.java) | Domain/model/configuration logic used by this module; follow references from its controller/entry point. |
| [src/main/resources/application-local.yaml](../../services/pricing-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/pricing-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/test/java/com/brokecart/pricing/PricingApiTest.java](../../services/pricing-service/src/test/java/com/brokecart/pricing/PricingApiTest.java) | Application unit/contract test; not proof of the deployed Kubernetes journey. |
| [src/test/java/com/brokecart/pricing/QuoteServiceTest.java](../../services/pricing-service/src/test/java/com/brokecart/pricing/QuoteServiceTest.java) | Application unit/contract test; not proof of the deployed Kubernetes journey. |
### reporting-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/reporting-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/reporting-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/reporting/ReportingApplication.java](../../services/reporting-service/src/main/java/com/brokecart/reporting/ReportingApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/reporting/ReportingController.java](../../services/reporting-service/src/main/java/com/brokecart/reporting/ReportingController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/reporting-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/reporting-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### returns-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/returns-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/returns-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/returns/ReturnsApplication.java](../../services/returns-service/src/main/java/com/brokecart/returns/ReturnsApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/returns/ReturnsController.java](../../services/returns-service/src/main/java/com/brokecart/returns/ReturnsController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/returns-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/returns-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### search-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/search-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/search-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/search/SearchApplication.java](../../services/search-service/src/main/java/com/brokecart/search/SearchApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/search/SearchController.java](../../services/search-service/src/main/java/com/brokecart/search/SearchController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/search-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/search-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |
### shipping-service

| File | What to inspect |
|---|---|
| [Dockerfile](../../services/shipping-service/Dockerfile) | Multi-stage Maven-to-JRE image for this selected module; non-root runtime. |
| [pom.xml](../../services/shipping-service/pom.xml) | Module dependencies/plugins and relationship to the parent reactor. |
| [src/main/java/com/brokecart/shipping/ShippingApplication.java](../../services/shipping-service/src/main/java/com/brokecart/shipping/ShippingApplication.java) | Spring Boot entry point and component scanning. |
| [src/main/java/com/brokecart/shipping/ShippingController.java](../../services/shipping-service/src/main/java/com/brokecart/shipping/ShippingController.java) | HTTP mappings and/or event handler; inspect auth, validation, transaction and state transitions. |
| [src/main/resources/application-local.yaml](../../services/shipping-service/src/main/resources/application-local.yaml) | Process defaults/common imports, dependency options and application service identity. |
| [src/main/resources/application.yaml](../../services/shipping-service/src/main/resources/application.yaml) | Process defaults/common imports, dependency options and application service identity. |

## Frontend and shared library

| Path | Purpose |
|---|---|
| [frontend/Dockerfile](../../frontend/Dockerfile) | Node/Vite build, then unprivileged Nginx static runtime. |
| [frontend/nginx.conf](../../frontend/nginx.conf) | Static SPA fallback, /health, explicit /api/ rejection and browser response headers. |
| [frontend/package.json](../../frontend/package.json) | npm scripts/dependency declarations; lockfile records resolved dependencies. |
| [frontend/package-lock.json](../../frontend/package-lock.json) | Repeatable npm ci dependency lock. |
| [frontend/vite.config.ts](../../frontend/vite.config.ts) | Frontend development/build configuration; local API forwarding differs from Kubernetes Kong routing. |
| [frontend/src/main.tsx](../../frontend/src/main.tsx) | React entry/root UI and navigation wiring. |
| [frontend/src/commerce.tsx](../../frontend/src/commerce.tsx) | Shopping/account/order/operator interface behavior. |
| [frontend/src/cart.ts](../../frontend/src/cart.ts) | Browser cart state helpers. |
| [frontend/src/cart.test.ts](../../frontend/src/cart.test.ts) | Cart helper unit tests. |
| [frontend/tests](../../frontend/tests) | Browser test scenarios, separate from live user acceptance. |
| [frontend/public/products](../../frontend/public/products) | Original static product illustrations served with the storefront. |
| [libraries/commerce-common](../../libraries/commerce-common) | Shared security, HTTP peers, persistence, Kafka transport and telemetry configuration; explained in chapter 6. |
| [tools/run-local.py](../../tools/run-local.py) | Explicit application-only development launcher using local-profile dependencies, not the kind deployment. |

## How to read an arbitrary manifest

`apiVersion`/`kind` selects the API resource type; `metadata.name` identifies the object; namespace gives its scope; labels support selection; annotations carry controller instructions; `spec` is desired configuration; `status` is controller-observed state and is not copied into hand-authored desired-state files. A label has no permission effect by itself. A Secret reference is not the Secret value. Read selectors, named ports and volume references on both ends when tracing dependencies.

Helm chart version must be valid SemVer, for example `0.1.0` (zero), not `0.1.o` (letter o). An INFO suggesting a chart icon is not a lint failure. A syntax-valid rendered manifest still needs runtime checks for credentials, certificates, DNS, capacity and business behavior.
