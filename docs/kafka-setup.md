# Kafka and Kafka UI

These files prepare the Kafka portion of BrokeCart for the later GitHub Actions/Argo CD delivery flow. They do not install applications into kind merely by being present in Git. The Argo CD Application manifests are not applied until the platform, health checks, and reviewed configuration are ready.

## What runs where

Catalog's application-chart integration is now being prepared. With `kafka.enabled=true`, it renders ServiceAccount `catalog-kafka-secrets`, SecretStore `catalog-kafka-openbao`, ExternalSecret `catalog-kafka-credentials`, and ConfigMap `catalog-kafka-config` in `brokecart-catalog`. The dedicated OpenBao role reads only `brokecart/catalog/kafka`.

ESO formats the login into the generated Secret's `sasl-jaas-config` key. The public ConfigMap contains the CA and Spring Kafka settings for SASL_SSL/PLAIN, PEM trust and hostname verification. The Deployment mounts this ConfigMap at `/etc/kafka-client`, populates `KAFKA_SASL_JAAS_CONFIG` from the Secret and sets `SPRING_CONFIG_ADDITIONAL_LOCATION=file:/etc/kafka-client/kafka.yaml` when Kafka is enabled. Rendering is checked; deployed application connectivity remains to be tested. Credential changes require an application rollout because these environment variables are read at startup.

| Component | Namespace | Kubernetes resources |
|---|---|---|
| Kafka | `brokecart-kafka` | Three-replica StatefulSet, per-Pod PVCs, bootstrap and headless Services, ServiceAccounts, SecretStore, ExternalSecrets, Certificate, ConfigMaps, provisioning Job, PDB |
| Kafbat UI | `brokecart-kafka-ui` | Deployment and Service from the pinned upstream chart, workload and ESO ServiceAccounts, SecretStore, two ExternalSecrets, public-CA ConfigMap, HTTPS HTTPRoute |

Kafka uses `apache/kafka:3.9.1`, matching the application's existing integration-test baseline. This is not a claim that it is the latest release. An upgrade should be explicitly tested and pinned. Kafbat's wrapper chart pins dependency `1.6.5` and image `ghcr.io/kafbat/kafka-ui:v1.5.0`.

Each Kafka Pod is both a broker and a KRaft controller:

```text
kafka-0 (node 0) -- data-kafka-0
kafka-1 (node 1) -- data-kafka-1
kafka-2 (node 2) -- data-kafka-2
```

Controllers maintain cluster metadata; brokers store messages. There is no ZooKeeper. Combined roles save local resources, but cannot be scaled or maintained independently. A production deployment commonly separates them.

Each PVC requests 5 Gi. Kafka JVM heap is 256–512 Mi per Pod, with a 1 Gi container limit. The three Pods share your physical machine's CPU and RAM; kind-node capacity must not be added together. Preferred anti-affinity spreads Pods when possible. Two worker nodes cannot place all three Pods on distinct workers, so quorum redundancy is not physical-host high availability.

`Parallel` Pod management allows quorum members to start together. Persistent claim retention is explicitly `Retain` on StatefulSet deletion and scale-down. Retained storage requires the same cluster ID and node ID. The startup script refuses identity mismatches rather than formatting a different cluster onto existing data. Do not change replica count casually: it also changes the static controller voter list and requires an explicit membership-change procedure.

## Networking and security

| Listener | Port | Security | Used by |
|---|---|---|---|
| CLIENT | 9092 | SASL/PLAIN over TLS | Applications, provisioning Job, Kafka UI |
| CONTROLLER | 9093 | Mutual TLS | Brokers/controllers |
| INTERNAL | 9094 | Mutual TLS | Broker replication |

Applications bootstrap through `kafka.brokecart-kafka.svc.cluster.local:9092`. Kafka returns broker-specific addresses under `kafka-headless.brokecart-kafka.svc.cluster.local`; clients must reach these too. Publishing unready headless addresses allows initial peer discovery.

cert-manager issues a certificate covering the bootstrap Service and each broker's fully qualified DNS name. A shared broker certificate with CN `brokecart-kafka` is used for this local cluster. Its server/client usages support mutual TLS on internal listeners. The Kafka superusers are the shared broker certificate identity and `kafka_admin`; application and UI logins are not superusers.

`Modern2023` PKCS#12 output produces a keystore and a truststore. The keystore contains the broker private key/certificate. The truststore contains the issuing CA. The provisioning Job mounts only the truststore. The UI mounts only the public root CA and uses Kafka's PEM truststore support. Hostname verification remains enabled.

The runtime server configuration is created under `/tmp` with owner-only permissions. It combines nonsecret ConfigMap settings, the broker's identity, and mounted credential files. It is never printed or committed. Do not enable shell tracing or dump this runtime configuration into logs.

SASL/PLAIN requires the broker to know the configured clients' passwords. Those are delivered through scoped ESO resources. For a future design that avoids storing plaintext client passwords on brokers, evaluate SCRAM and its separate credential-provisioning lifecycle. The current setup uses TLS to protect PLAIN credentials in transit.

## OpenBao and ESO

| OpenBao path | Contents | Reader |
|---|---|---|
| `brokecart/kafka/broker` | PKCS#12 password | Kafka ESO identity |
| `brokecart/kafka/admin` | Kafka administrator login | Kafka ESO identity |
| `brokecart/<service>/kafka` | Individual service login | Kafka ESO identity and the corresponding scoped application identity |
| `brokecart/kafka-ui/kafka` | Read-only UI Kafka login | Kafka ESO identity and UI ESO identity |
| `brokecart/kafka-ui/auth` | Browser login | UI ESO identity only |

`kafka-secrets` is bound to `brokecart-kafka`. It reads the broker configuration and client logins needed for server authentication. `kafka-ui-secrets` is bound to `brokecart-kafka-ui` and reads only the UI's two paths. Application identities use `<service>-kafka-secrets` in their respective namespaces. Kubernetes workload ServiceAccounts and ESO authentication ServiceAccounts have separate purposes.

The broker chart renders 16 ExternalSecrets: one combines broker/admin settings, and 15 deliver individual logins (14 backends plus the UI). The UI chart has two ExternalSecrets for its browser and Kafka connections.

The UI's ExternalSecret builds a JAAS string inside the generated Secret, using ESO templating. Helm only renders the template, never the password. UI values reference that Secret through environment variables. Its browser credentials are distinct from its Kafka credentials.

### Bootstrap once, rerun safely

OpenBao must be initialized, unsealed, and have the `secret` KV-v2 engine and Kubernetes authentication configured, as already established for this project. From WSL:

```bash
bash infra/bootstrap/run-kafka-bootstrap.sh
```

Enter the bootstrap/root token only at the hidden prompt. The runner sends it over stdin to a short-lived process in `openbao-0`, runs both scripts, and exits. It does not put the token into command arguments, files, Git, or a Kubernetes Secret.

`kafka-credentials.sh` preserves existing readable credentials and uses CAS=0 for new keys. A soft-deleted KV key with retained metadata will fail creation rather than silently replacing history. Investigate that path explicitly. `kafka-access.sh` reapplies named policies and roles. Re-running the scripts adds new UI credentials while preserving existing application passwords.

The two source scripts contain no generated credentials. Do not commit OpenBao initialization output, root tokens, unseal keys, kubeconfigs, or private keys.

## Topics and permissions

The chart provisions the nine application topics listed in `values.yaml`, plus matching `.DLT` topics: 18 topics total. Defaults are three partitions, replication factor three, minimum ISR two, and 72-hour retention. With producer `acks=all`, two in-sync replicas are required to acknowledge writes. Two lost replicas stop writes; they do not lower the durability requirement automatically.

Partitions allow parallel processing; ordering is per partition. The application keys events by aggregate ID. Consumers use separate groups named after their Spring application, such as `orders-service`. All replicas of one service join that same group. DLT partition counts must match their source topics because the application's error handler retains the original partition number.

| Service | Produces | Consumes |
|---|---|---|
| catalog | catalog.events | — |
| inventory | inventory.events | inventory.commands, orders.events |
| orders | orders.events, inventory.commands, payments.commands, shipping.commands | inventory.events, payments.events, shipping.events, returns.events |
| payments | payments.events | payments.commands |
| shipping | shipping.events | shipping.commands |
| returns | returns.events, payments.commands, inventory.commands | payments.events |
| notifications | — | orders.events, shipping.events, returns.events |
| search | — | catalog.events |
| reporting | — | orders.events |

The ACL script grants exact topic writes/reads, exact consumer-group access, DLT writes for consumers, and cluster IdempotentWrite for these applications. Read/Write topic ACLs imply Describe in Kafka. Other application credentials have no topic permissions until required.

The UI receives read access and DescribeConfigs for the 18 application/DLT topics, group Describe for viewing consumer lag, and cluster Describe/DescribeConfigs for inspecting brokers. It receives no topic Write/Create/Delete/Alter, no consumer-group Read/offset commit permission, and no IdempotentWrite. Its manual-assignment message browser does not join application consumer groups. The UI also has `readOnly: true` and dynamic configuration disabled. Inspection of topics/brokers/messages is supported; modifying topics, publishing messages, resetting offsets, and editing ACLs are intentionally unavailable.

Provisioning is additive: `--if-not-exists` preserves existing topics, and ACL adds are repeatable. Changing a topic's desired partitions/replicas/retention or removing an ACL entry from values does not automatically reconcile that live change. Perform explicit reviewed topic changes or ACL revocations. Bootstrap assumes generated usernames match the naming convention in the ACL template.

## Argo CD sequencing

Within the Kafka Application:

```text
-3 ServiceAccounts
-2 SecretStore
-1 ExternalSecrets and Certificate
 0 Services, ConfigMaps, PDB
 1 Kafka StatefulSet
 2 Sync-hook Job: wait for authenticated API, create topics, apply ACLs
```

Argo CD must first be installed using `infra/platform/argocd-values.yaml`, including health checks for SecretStore, ExternalSecret, and Certificate. Wave ordering alone does not prove readiness. Missing OpenBao credentials keep the early resources unready rather than allowing provisioning to succeed.

`infra/argocd/applications/kafka.yaml` and `kafka-ui.yaml` point to the charts in Git. Do not apply them until the planned delivery stage. Argo CD renders Helm charts and manages Kubernetes resources; this does not create Helm CLI release-history Secrets, so Argo-managed applications will not appear as Helm-installed releases in `helm list`.

The two Applications are independent: resource waves inside one do not sequence another. The UI can start while Kafka is unavailable and reports the cluster offline until it can connect. If a parent deployment later needs strict cross-Application sequencing, configure parent Application health/dependency handling rather than relying on these child waves alone.

The hook Job is recreated for full synchronizations and removed on success. Failures remain available for diagnostics. Do not use selective resource sync for operations that require the provisioning hook.

## Browser access after automated deployment

Add this Windows hosts entry if absent:

```text
127.0.0.1 kafka.brokecart.com
```

Open `https://kafka.brokecart.com:8443`. The existing Kong wildcard certificate covers the hostname. Trust the existing BrokeCart root CA in the browser as already done for Grafana/OpenBao. The HTTPRoute attaches only to the Gateway's HTTPS listener and forwards to the UI's ClusterIP Service. Kafka broker ports are not exposed through this HTTPRoute.

Find the UI browser username/password in OpenBao at `secret` → `brokecart/kafka-ui/auth`. Kafka administrator credentials are not used for browser login.

## Validation before deployment

```bash
helm dependency build infra/charts/kafka-ui
helm lint infra/charts/kafka
helm lint infra/charts/kafka-ui
python3 tests/kafka_configuration.py
```

The configuration check renders both charts, checks mounts and private client configuration, executes the ACL script against a capturing fake CLI, checks the exact intended permissions, and rejects invalid quorum/replication settings. It never contacts Kubernetes or OpenBao. It needs Python's PyYAML package.

For actual TLS, ACL, failover, and UI login verification, with Docker access and several GiB free:

```bash
python3 tests/kafka_runtime.py
```

This uses disposable Docker containers, synthetic credentials and a test CA, not the project's real CA or secrets. It starts three Kafka nodes, runs the rendered provisioning scripts, tests allowed/denied access, launches Kafbat with browser authentication, and stops one Kafka node to test continued writes. It cleans only its uniquely labelled fixtures. This proves container/runtime behavior, not kind scheduling, ESO connectivity, Kong routing, or Argo CD synchronization; those remain deployment-stage checks.

The dependency archive under `infra/charts/kafka-ui/charts/` is downloaded and ignored in Git. Keep Chart.yaml and Chart.lock in Git. Argo CD or CI must be able to restore the pinned dependency from the repository.

### Verification recorded on 2026-10-18

- Both charts passed Helm lint and rendering.
- `tests/kafka_configuration.py` passed: resource wiring, scoped Secret access, exact application/UI ACLs, private client configuration, and rejection of invalid quorum/replication settings.
- `tests/kafka_runtime.py` passed using three disposable Kafka containers and a disposable Kafbat container: TLS/admin startup; all 18 topics with three partitions/replicas; orders-to-inventory delivery; rejected unauthorized writes, wrong passwords and hostname mismatches; read-only UI Kafka access; authenticated browser login and topic browsing; and continued `acks=all` writes after stopping one combined broker/controller.
- OpenBao bootstrap added the two UI credential paths and its scoped role/policy while retaining existing Kafka passwords.

These are completed configuration/container tests. The charts and Argo CD Applications have not been deployed into kind. ESO synchronization, certificate issuance with the real issuer, Kong browser access and cluster-specific scheduling will be verified during the agreed automated deployment stage.

## Operations and troubleshooting after deployment

```bash
kubectl --context kind-brokecart -n brokecart-kafka get pods,pvc,secretstores,externalsecrets,certificates,pdb
kubectl --context kind-brokecart -n brokecart-kafka logs kafka-0 --tail=60
kubectl --context kind-brokecart -n brokecart-kafka get jobs
kubectl --context kind-brokecart -n brokecart-kafka-ui get deployments,pods,externalsecrets,httproutes
```

For `namespace not authorized`, verify the OpenBao role's exact ServiceAccount and namespace. For missing Secret keys, verify bootstrap paths/properties and ESO conditions. For TLS failures, inspect certificate readiness, DNS SANs, CA trust and keystore-password consistency. Do not disable hostname verification to conceal a mismatch. TopicAuthorization errors indicate missing topic ACLs; GroupAuthorization errors indicate a wrong or missing consumer-group ACL.

TCP probes only establish listener availability; they do not prove quorum or replication health. Inspect broker health, partition leaders, ISR and consumer lag. Prometheus/JMX and alert rules belong to the later stack-wide observability wiring; the UI is not a replacement for those checks.

The PDB permits at most one healthy broker to be voluntarily disrupted at a time. It does not prevent crashes, guarantee node failure isolation, or replace quorum monitoring. Kafka's StatefulSet update process and administrative maintenance must also preserve quorum.

ConfigMap/startup-script checksum changes roll Pods. ESO updates do not automatically rebuild SASL files or restart processes. Password changes need a coordinated credential rollout; scripts intentionally avoid automatic rotation. Likewise plan a controlled broker rollout after certificate renewal, and verify internal/client TLS before the next broker restarts. Keep CA/key material protected and plan recovery separately; replication and a PVC are not backups.
