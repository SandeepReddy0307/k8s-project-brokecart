# 5. PostgreSQL, Redis, Kafka, Elasticsearch and Kafka UI

[Index](README.md) · [Previous](04-observability.md) · [Next: application services](06-services.md)

## How these are installed

The following charts are owned by Argo CD. Review them now; activate the root Application using chapter 7 after bootstrap credentials and images are ready. Do not also install independent Helm CLI releases for them.

| Component | Chart | Namespace | Persistent storage |
|---|---|---|---|
| PostgreSQL 16.15 | `infra/charts/postgres` | brokecart-postgres | 1 × 5Gi |
| Redis 7.4.11 | `infra/charts/redis` | brokecart-redis | 1 × 2Gi |
| Kafka 3.9.1 | `infra/charts/kafka` | brokecart-kafka | 3 × 5Gi |
| Elasticsearch 8.17.6 | `infra/charts/elasticsearch` | brokecart-elasticsearch | 1 × 5Gi |
| Kafbat UI 1.5.0 | Wrapper `infra/charts/kafka-ui`, dependency chart 1.6.5 | brokecart-kafka-ui | No business-data PVC |

All PVCs are node-local kind storage; deleting/recreating a node or cluster is not a persistence test. Review the tested image pins when upgrading rather than treating them as “latest”.

`volumeClaimTemplates` creates a separate named PVC for each StatefulSet ordinal; for example template `data` plus StatefulSet Pod `kafka-1` yields `data-kafka-1`. The local-path provisioner creates the backing node directory/PV after scheduling identifies a consumer. PV node affinity then ties the volume to that node; scheduling it on another node does not copy its data. `ReadWriteOnce` means read-write mounting by one node, not necessarily exactly one Pod on that node. A PVC's requested 5Gi is storage capacity, not 5Gi RAM and not a replica of the data elsewhere. Inspect both claim and PV when diagnosing storage:

```bash
kubectl --context kind-brokecart -n brokecart-postgres describe pvc data-postgres-0
kubectl --context kind-brokecart get pv
kubectl --context kind-brokecart get storageclass standard -o yaml
```

## PostgreSQL: one server, separate application databases

All 14 HTTP services share one PostgreSQL process, but each has its own database and non-superuser account. Catalog uses database `catalog` and user `brokecart_catalog`; payment-provider uses `payment_provider` and `brokecart_payment_provider`. Separate databases/users reduce accidental access; they do not isolate CPU, memory or total server connection capacity.

### Resources and order

1. ServiceAccounts `postgres`, `postgres-secrets`, `database-provisioner`.
2. SecretStore `openbao` retrieves admin credentials; `openbao-provisioning` has explicit permission for the 14 application DB credential paths.
3. ExternalSecret `postgres-admin` and 14 service credential ExternalSecrets deliver those values into the **PostgreSQL namespace** for trusted provisioning.
4. Certificate `postgres` creates `postgres-tls` from the local ClusterIssuer.
5. Services `postgres` and `postgres-headless`, provisioning ConfigMap, NetworkPolicy.
6. StatefulSet `postgres`, Pod `postgres-0`, PVC `data-postgres-0`.
7. Sync-hook Job `postgres-provisioning` creates/updates the 14 roles and databases.

Application namespaces also get their own copies of their own DB credentials through their own scoped ExternalSecrets. Kubernetes Secrets cannot be directly referenced across namespaces.

### Why two Services?

`postgres` is the application's stable ClusterIP endpoint. `postgres-headless` is the StatefulSet governing discovery Service, without a virtual ClusterIP. A StatefulSet needs a stable network identity even though a single-server client only needs the regular Service.

### Storage and mounts

| Mount | Backing object | Purpose |
|---|---|---|
| `/var/lib/postgresql/data` | `data-postgres-0` PVC | Persistent database files; PGDATA is its `/pgdata` subdirectory |
| `/var/run/postgresql` | emptyDir `runtime` | Writable socket/runtime files |
| `/tmp` | emptyDir `tmp` | Temporary files with a read-only root filesystem |
| `/etc/postgres-tls` | Secret `postgres-tls`, read-only | Server certificate, private key, CA |

The Pod runs as UID/GID 70 with fsGroup 70, drops capabilities and denies privilege escalation. `defaultMode: 0440` supplies restrictive mounted key permissions. A named `volumeMount` tells a container where to access a volume; the matching `volumes`/`volumeClaimTemplates` defines its source. `emptyDir` survives a container restart inside the same Pod but disappears with Pod replacement; PVC data has a separate lifecycle.

### Provisioning versus migrations

The PostgreSQL init environment creates the initial administrator/database only when its data directory is empty. Changing `POSTGRES_PASSWORD` in a Secret does not automatically change an existing PostgreSQL role password.

`provisioning-configmap.yaml` provides shell/SQL that reads mounted credentials, safely quotes role identifiers/password values, refuses system databases/admin modification, creates missing application databases, restricts users and revokes PUBLIC database access. Re-running it updates managed application role passwords from the provider values. Do not change provider credentials casually: this is a coordinated rotation operation.

Flyway runs inside each Java application at startup to create/update its tables. The database provisioning Job does not apply application Flyway migrations. BrokeCart therefore does not have the separate per-service migration Jobs seen in the earlier Streamflix project.

### Connection budgeting

PostgreSQL currently allows 100 connections. Each backend pool is capped at two, with minimum idle one. Fourteen one-replica services permit 28 pooled connections, leaving space for migrations, admin and PostgreSQL processes. Previously five connections per Pod across many two-replica services exhausted the server.

Increasing `max_connections` consumes resources and should not be the first response to oversized mostly-idle pools. Recalculate the whole-cluster pool budget before adding replicas or load tests.

```bash
kubectl --context kind-brokecart -n brokecart-postgres get statefulsets,pods,services,pvc
kubectl --context kind-brokecart -n brokecart-postgres get secretstores,externalsecrets,certificates,jobs
kubectl --context kind-brokecart -n brokecart-postgres exec postgres-0 -- \
  sh -ec 'psql -U "$POSTGRES_USER" -d postgres -c "SHOW max_connections;" -c "SELECT usename, state, count(*) FROM pg_stat_activity GROUP BY usename, state ORDER BY count(*) DESC;"'
```

The local socket admin query above does not verify network TLS. This explicit check does:

```bash
kubectl --context kind-brokecart -n brokecart-postgres exec postgres-0 -- sh -ec \
  'PGPASSWORD="$POSTGRES_PASSWORD" psql "host=postgres.brokecart-postgres.svc.cluster.local port=5432 dbname=postgres user=$POSTGRES_USER sslmode=verify-full sslrootcert=/etc/postgres-tls/ca.crt" -c "SELECT current_user, current_database(), ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid();"'
```

Expect `ssl = t`. Java clients also use `sslmode=verify-full` and a mounted public CA. Database traffic is authenticated and encrypted; not every arbitrary Pod has ingress permission to PostgreSQL.

## Redis: shared authenticated carts

Cart is the only backend with Redis enabled. Logged-in carts must survive replacing a Cart Pod; Redis holds this shared cart state. Guest carts remain browser-local and merge on login.

Resources: StatefulSet/Pod `redis`/`redis-0`, normal/headless Services, PVC, config ConfigMap, workload and secret-login ServiceAccounts, SecretStore, ExternalSecret `redis-auth`, and NetworkPolicy. The backend Cart chart creates its own scoped Redis credentials in `brokecart-cart`.

`redis.conf` enables AOF persistence with `appendfsync everysec`, disables periodic RDB snapshots, sets a 128mb data limit and `noeviction`. Refusing a new write when full is preferable to silently evicting active cart data, but the application still needs to handle that write error. The container limit is 256Mi, leaving overhead beyond the data cap; AOF rewrites can need more headroom.

Password material is combined with public Redis configuration at runtime, not committed in the ConfigMap. Current transport is password-authenticated **plain TCP**, not Redis TLS. The NetworkPolicy permits Cart's namespace and Redis's own namespace; it is not a replacement for encryption outside this local boundary.

```bash
kubectl --context kind-brokecart -n brokecart-redis get statefulsets,pods,services,pvc
kubectl --context kind-brokecart -n brokecart-redis exec redis-0 -- sh -ec \
  'redis-cli -h 127.0.0.1 PING'
```

The Redis Pod already receives `REDISCLI_AUTH` from its Secret; redis-cli uses that environment variable. Do not pass a password with `redis-cli -a ...` in examples or terminal screenshots.

## Kafka: three-node KRaft

### Brokers, controllers, topics and partitions

Each Pod runs both `broker` and `controller` roles. There are three Pods: `kafka-0`, `kafka-1`, `kafka-2`; their ordinal becomes the Kafka node ID. KRaft stores cluster metadata without ZooKeeper. The configured static quorum lists those three controller endpoints.

The StatefulSet uses parallel Pod startup and stable DNS such as:

```text
kafka-0.kafka-headless.brokecart-kafka.svc.cluster.local
```

The headless Service publishes not-ready addresses for peer discovery. The ordinary `kafka` Service is a bootstrap endpoint; clients obtain broker metadata and then connect to the advertised individual broker addresses. Advertising `localhost` or a workstation address would break in-cluster clients.

A topic is an ordered collection split into partitions. Ordering is within one partition, not globally across a whole topic. Records use aggregate/order ID as key, keeping related records together. Replication factor three copies each partition's data across three brokers. These are three logical replicas on one laptop, not separate physical failure domains.

| Setting | Value | Effect |
|---|---:|---|
| Broker/controller Pods | 3 | Metadata quorum can tolerate one unavailable member |
| Partitions per application topic | 3 | Up to three active consumers per topic per group |
| Replication factor | 3 | Three replicas of each partition |
| Minimum in-sync replicas | 2 | Producer `acks=all` requires enough current replicas |
| Retention | 72h | Time-based record retention |
| Auto topic creation | Disabled | Provisioning owns topic creation |
| Unclean leader election | Disabled | Avoid electing a stale out-of-sync leader |
| Kafka PDB | minAvailable 2 | Limits voluntary disruptions |

Do not scale this existing quorum down to one by changing only `replicaCount`. Stored cluster/node IDs, static voters, topic RF and min ISR would also need a planned migration. We retained three Kafka nodes while reducing backend replicas.

### Ports and security

| Listener | Port | Transport/authentication |
|---|---:|---|
| CLIENT | 9092 | SASL_SSL with PLAIN credentials over verified TLS |
| CONTROLLER | 9093 | TLS with client certificate authentication |
| INTERNAL | 9094 | Inter-broker TLS with client certificates |

cert-manager issues a certificate covering bootstrap/headless/individual broker names and PKCS12 stores. The startup script builds private `/tmp/server.properties` with mounted credentials, validates stored cluster/node IDs, formats only unformatted storage and starts Kafka. `StandardAuthorizer` defaults to deny when no ACL permits access.

### Topics and exact users

| Topic | Producers | Consumers |
|---|---|---|
| catalog.events | catalog | search |
| inventory.commands | orders, returns | inventory |
| inventory.events | inventory | orders |
| payments.commands | orders, returns | payments |
| payments.events | payments | orders, returns |
| shipping.commands | orders | shipping |
| shipping.events | shipping | orders, notifications |
| orders.events | orders | inventory, notifications, reporting |
| returns.events | returns | orders, notifications |

Each has a matching `.DLT`, so there are 18 application topics in total, each with three partitions. Consumers have distinct service groups (`orders-service`, `returns-service`, etc.). Each group can read its copy independently; adding a second service to the same group would instead divide that group's partitions.

### Provisioning and ACLs

Job `kafka-topic-provisioning` runs after broker readiness, creates missing topics, then applies per-principal write/read/group permissions. It grants DLT write permission for consumed topics and read-only inspection rights to the Kafka UI identity. Topic creation is create-if-missing; changing values does not automatically reassign existing partitions or change every existing topic setting. ACL additions also do not revoke every historical grant.

The Job is an Argo `Sync` hook at wave 2, with a 900s deadline and cleanup after success. A slow Job is not automatically stuck: each CLI ACL operation starts a JVM, so sequential setup can take minutes on a laptop. Inspect progress before restarting it. `HookSucceeded` cleanup means a missing successful Job later is expected.

```bash
kubectl --context kind-brokecart -n brokecart-kafka get statefulsets,pods,pvc,certificates,pdb
kubectl --context kind-brokecart -n brokecart-kafka get jobs
kubectl --context kind-brokecart -n brokecart-kafka logs -f job/kafka-topic-provisioning --tail=20
```

The logs command only works while the hook still exists. To inspect topics later without printing credentials, copy the **public helper script** and let it read mounted credentials inside a broker:

```bash
kubectl --context kind-brokecart -n brokecart-kafka cp \
  infra/charts/kafka/files/admin-client.sh kafka-0:/tmp/brokecart-admin-client.sh

kubectl --context kind-brokecart -n brokecart-kafka exec -i kafka-0 -- bash -s <<'KAFKA'
export CLIENT_CONFIG="/tmp/brokecart-inspect-$$.properties"
source /tmp/brokecart-admin-client.sh
trap 'rm -f "$CLIENT_CONFIG"' EXIT
/opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka.brokecart-kafka.svc.cluster.local:9092 \
  --command-config "$CLIENT_CONFIG" --describe
/opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka.brokecart-kafka.svc.cluster.local:9092 \
  --command-config "$CLIENT_CONFIG" --list
KAFKA
```

Do not print the generated properties file: it contains a password. Use the read-only UI for ordinary learning rather than administrative CLI permissions everywhere.

### Kafka UI

```bash
helm repo add kafbat https://kafbat.github.io/helm-charts
helm dependency build infra/charts/kafka-ui
helm lint infra/charts/kafka-ui
```

`Chart.lock` pins the dependency; the downloaded chart archive is not committed. Argo deploys the wrapper into `brokecart-kafka-ui` at parent wave 5. The wrapper supplies ServiceAccounts, SecretStore, UI login ExternalSecret, Kafka client ExternalSecret, public CA ConfigMap and HTTPRoute. The upstream dependency renders the UI Deployment/Service.

Open `https://kafka.brokecart.com:8443/`. Browser credentials come from `brokecart/kafka-ui/auth`; broker access uses a separate identity from `brokecart/kafka-ui/kafka`. Read-only UI plus Kafka ACLs prevents writes through this user; a UI checkbox alone is not the authorization boundary.

## Elasticsearch: authenticated search projection

One StatefulSet Pod stores a 5Gi product index with one primary shard and zero replica shards. No replica is appropriate to this single-node local setup but provides no ES redundancy. Heap is 512Mi within a 1536Mi container. `node.store.allow_mmap: false` avoids relying on a privileged sysctl adjustment for this local baseline.

The chart mounts TLS beneath Elasticsearch's config directory, creates writable config/log/tmp volumes around a read-only root filesystem, and starts as UID 1000. `prepare-config.sh` copies the image configuration; `start.sh` reads the mounted admin password and exports the required runtime bootstrap variable. It does not disable authentication to make probes pass.

Job `elasticsearch-provisioning` creates native role/user `brokecart_search` with read/write/create-index access to **only** `brokecart-products`; no security or cluster admin rights. It preserves an existing index rather than deleting/recreating data. `search-role.json` and `product-index.json` describe the permissions and mapping/settings.

Search imports the public local CA into a Java truststore via an init container; Java's HTTP client validates the ES server certificate and hostname. This is separate from OpenBao's ESO CA bundle.

The readiness script uses an authenticated CA-verified health request with:

```text
--resolve elasticsearch:9200:127.0.0.1
```

This retains certificate hostname verification but checks the local process. An unready Pod cannot depend on its regular Service's ready endpoints to become ready; that circular dependency was a real deployment bug and is now fixed.

```bash
kubectl --context kind-brokecart -n brokecart-elasticsearch \
  get pods,pvc,certificates,secretstores,externalsecrets,jobs
kubectl --context kind-brokecart -n brokecart-elasticsearch \
  logs elasticsearch-0 -c elasticsearch --tail=40
kubectl --context kind-brokecart -n brokecart-elasticsearch \
  exec elasticsearch-0 -c elasticsearch -- /bin/sh /scripts/check-ready.sh
```

An exit code 0 from that last command verifies the actual probe without printing its credentials. The provisioning hook is deleted after success. The `elastic` password on a populated data volume is not rotated just by editing its original bootstrap Secret.
