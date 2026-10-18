# Elasticsearch setup

Elasticsearch stores the product search index. PostgreSQL remains the application's database; Kafka catalog events cause search-service to update Elasticsearch. This is separate from Loki, which stores application logs.

The configuration is ready for the planned Argo CD deployment. Creating these files does not install Elasticsearch in kind. OpenBao bootstrap is a separate, one-time prerequisite.

## Files and resources

Chart: `infra/charts/elasticsearch`. Argo CD Application: `infra/argocd/applications/elasticsearch.yaml`. Destination namespace: `brokecart-elasticsearch`.

| Resource | Purpose |
|---|---|
| StatefulSet elasticsearch | One Elasticsearch process with a stable Pod name |
| PVC data-elasticsearch-0 | 5 GiB product-index and security-index storage |
| Service elasticsearch | Internal HTTPS endpoint on port 9200 |
| Service elasticsearch-headless | StatefulSet network identity |
| ServiceAccount elasticsearch | Workload identity, without an automatically mounted API token |
| ServiceAccount elasticsearch-secrets | Identity ESO uses to authenticate to OpenBao |
| SecretStore openbao | OpenBao HTTPS URL, CA and Kubernetes authentication role |
| Two ExternalSecrets | Deliver administrator and search-user credentials into this namespace |
| Certificate elasticsearch | cert-manager issues the internal server certificate |
| ConfigMaps | Non-secret configuration, startup scripts, role and index definitions |
| Job elasticsearch-provisioning | Creates/updates search-user permissions and creates a missing product index |

One node fits this shared local machine. It is not highly available. The product index uses one primary shard and zero replicas; setting replicas above zero on one node leaves replicas unassigned. PVC retention preserves data when the StatefulSet is removed, but deleting the PVC with the standard StorageClass can delete the underlying data.

The image is pinned to `8.17.6`, matching the existing application integration-test baseline. This is not a claim that it is the latest supported or security-patched Elastic release. Review and test an upgrade before using this configuration outside the learning environment.

## Configuration and startup

Values select the image, storage, resources, OpenBao paths and TLS issuer. Defaults reserve 768 MiB RAM, limit the process container to 1536 MiB, and set a 512 MiB Java heap. These share the host's RAM with Kafka and the rest of the project.

The init container copies the image's default config into an emptyDir and adds our elasticsearch.yml. Elasticsearch needs writable configuration for its keystore; its root filesystem remains read-only. Data has a PVC; temporary files and logs use emptyDir. Console logs remain available to Fluent Bit.

The process runs as UID 1000. It reads the mounted administrator password and passes it privately through the official entrypoint's environment. The password is not embedded in values, ConfigMaps or command arguments. We avoid the image's `ELASTIC_PASSWORD_FILE` option because it rejects group-readable projected Secret permissions.

`node.store.allow_mmap: false` avoids a privileged init container or host sysctl changes on this local cluster. This trades away mmap performance. For production workloads Elastic recommends enabling mmap with an appropriately configured host; see [Elastic virtual-memory guidance](https://www.elastic.co/docs/deploy-manage/deploy/cloud-on-k8s/virtual-memory).

HTTP and transport TLS are enabled. TLS files mount beneath Elasticsearch's configuration directory. Clients must trust the local root CA and verify the service DNS name. No public Gateway route is created for Elasticsearch, and there is no Kibana deployment in this step.

## Credentials and access

| OpenBao KV v2 path | Fields | Reader |
|---|---|---|
| brokecart/elasticsearch/admin | username=elastic, password | Elasticsearch namespace only |
| brokecart/search/elasticsearch | username=brokecart_search, password | Provisioning Job and future search-service secret delivery |

The server ESO role `elasticsearch-secrets` is bound to the same-named ServiceAccount in `brokecart-elasticsearch`. Its policy can read these two paths.

The future application role `search-elasticsearch-secrets` is bound to the same-named ServiceAccount in `brokecart-search`. Its policy can read only the search credential. The search application's chart still needs to create its ExternalSecret/ServiceAccount/SecretStore wiring.

The Job authenticates as elastic to create a native role/user. The search role can read, write and create only `brokecart-products`. It cannot administer users or access other indices. The application currently attempts to create that index before indexing products, which is why create_index is included.

Provisioning precreates mappings matching the application and the single-node index settings. Running it again updates the restricted role and user password but keeps an existing index and its data. It does not migrate existing mappings or reconcile index settings.

## Bootstrap OpenBao

Run from the repository root:

```bash
bash infra/bootstrap/run-elasticsearch-bootstrap.sh
```

Enter an authorized OpenBao administrator token at the hidden prompt. The launcher passes it over stdin to a temporary process in openbao-0; it does not write it into Git or a Kubernetes Secret.

The scripts create two random passwords and the scoped policies/roles. Existing readable credentials are retained. Creation uses KV check-and-set 0 to avoid silently overwriting credentials. A soft-deleted path can require deliberate recovery; do not erase metadata simply to make bootstrap pass.

This bootstrap has not been run automatically as part of preparing the chart. Do not put an OpenBao root token in routine application CI.

## Deployment ordering

Argo CD waves within this Application:

1. Wave -3: ServiceAccounts.
2. Wave -2: SecretStore.
3. Wave -1: ExternalSecrets and Certificate.
4. Wave 0: Services and ConfigMaps.
5. Wave 1: StatefulSet.
6. Wave 2: provisioning Sync-hook Job.

Use the existing Argo CD health customizations in `infra/platform/argocd-values.yaml` so Argo waits for ESO Secrets and certificates. These waves do not order separate Applications. Later application readiness/retries and deployment orchestration must account for dependency availability.

The bootstrap password initializes Elasticsearch security. Editing the administrator password in OpenBao does not rotate an already initialized Elasticsearch administrator account: use Elasticsearch's password API and coordinate Secret changes. The provisioning Job can reconcile the search user's password; running applications also need a coordinated credential refresh.

cert-manager renews the TLS Secret; verify reload behavior and readiness after renewal. This chart does not implement a certificate reloader or a complete CA-rotation workflow.

## Search application wiring still to do

When completing the application Helm chart:

- Set SEARCH_BACKEND=elasticsearch.
- Set ELASTICSEARCH_URL=https://elasticsearch.brokecart-elasticsearch.svc.cluster.local:9200.
- Supply ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD from the search-only generated Secret.
- Import the public local root CA into the Java truststore used by search-service's JDK HttpClient, with hostname verification retained. Mounting a PEM file alone does not configure Java trust.
- Configure Kafka catalog.events consumption and the search database separately.
- Add network policies allowing search-service to reach this endpoint.

This step tests the Elasticsearch dependency directly; it does not yet verify the deployed Java application's HTTPS integration.

## Verification

On 2026-10-18, Helm lint, the 12-resource configuration check and the disposable runtime test passed. The runtime test verified repeatable provisioning, product indexing/search, permission denials, TLS trust and document/native-user persistence after container restart. Its fixture was removed afterward. Elasticsearch has not been deployed into kind by this step.

Offline checks:

```bash
helm lint infra/charts/elasticsearch
python3 tests/elasticsearch_configuration.py
git diff --check
```

Disposable Docker runtime verification:

```bash
python3 tests/elasticsearch_runtime.py
```

The runtime test uses fresh synthetic credentials and a temporary certificate, the rendered chart config/scripts, UID 1000, a read-only root filesystem and a 1536 MiB limit. It checks provisioning twice, authenticated document indexing/search, rejection of unrelated indices and user administration, incorrect passwords, TLS trust, and persistence after restart. It removes its own container and temporary files. It does not access kind, OpenBao, or real credentials.

After eventual deployment:

```bash
kubectl --context kind-brokecart -n brokecart-elasticsearch get pods,pvc,certificates,secretstores,externalsecrets
kubectl --context kind-brokecart -n brokecart-elasticsearch logs elasticsearch-0
```

A successful Argo sync includes the provisioning hook's completion. If a hook fails, inspect its Job/Pod logs before retrying. Startup/readiness uses an authenticated, CA-verified cluster-health request; liveness checks the TCP listener. Secret rotation, backups/snapshots, Elasticsearch metrics export and cluster-wide network policies remain later work.
