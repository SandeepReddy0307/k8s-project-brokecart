# 4. Metrics, logs, traces and alerts

[Index](README.md) · [Previous](03-secrets.md) · [Next: datastores](05-data-services.md)

## Three signals, three storage systems

```text
Metrics: Prometheus scrapes Service -> /actuator/prometheus -> stores samples
Logs:    container stdout -> node log files -> Fluent Bit -> Loki gateway -> Loki
Traces:  Java spans -> OTel Collector :4318/v1/traces -> Tempo :4317
View:    browser -> Grafana -> queries Prometheus, Loki and Tempo
Alerts:  Prometheus evaluates rules -> Alertmanager groups/routes notifications
```

Grafana is the viewer. It does not collect container logs from nodes or replace Prometheus/Tempo/Loki storage. Metrics Server is for resource metrics/HPA and is independent of this retained monitoring stack.

## Step 1: monitoring stack

```bash
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --version 92.3.0 --kube-context kind-brokecart \
  --namespace observability --create-namespace \
  -f infra/platform/monitoring-values.yaml --wait --timeout 10m

kubectl --context kind-brokecart -n observability get pods,pvc
kubectl --context kind-brokecart -n observability \
  get prometheus,alertmanager,servicemonitors
kubectl --context kind-brokecart apply -f infra/platform/grafana-route.yaml
```

This chart installs several components, not one Prometheus Pod:

| Component | Job | Kubernetes form |
|---|---|---|
| Prometheus Operator | Watches monitoring CRs and creates/reconciles workloads | Deployment with RBAC/CRDs |
| Prometheus | Scrapes/stores metrics and evaluates rules | Operator-managed StatefulSet with PVC |
| Alertmanager | Groups, deduplicates and routes firing alerts | Operator-managed StatefulSet with PVC |
| Grafana | Dashboard and Explore UI | Deployment with persistent database and sidecars |
| kube-state-metrics | Exposes Kubernetes object state as metrics | Deployment |
| node-exporter | Exposes operating-system metrics | DaemonSet |
| kubelet/cAdvisor | Exposes container resource statistics | Existing kubelet endpoints scraped by Prometheus |

`monitoring-values.yaml` gives Prometheus a 5Gi PVC, three-day retention and a 4GB size retention target. Grafana has a 1Gi PVC; Alertmanager has 1Gi. Global Prometheus scrape/evaluation intervals are 30s; **backend ServiceMonitors override their scrape interval to 60s** for this laptop. Kind control-plane component monitors for scheduler/controller-manager/etcd/kube-proxy are disabled in these values. A disabled monitor is not a disabled Kubernetes component.

### Grafana browser login

Open `https://grafana.brokecart.com:8443/`, username `admin`. Read the current Kubernetes login Secret locally if using the chart-generated initial credential:

```bash
kubectl --context kind-brokecart -n observability get secret monitoring-grafana \
  -o jsonpath='{.data.admin-password}' | base64 --decode
echo
```

Changing that Secret alone does not necessarily update the password in Grafana's existing persistent database. We reset the database password using the CLI through stdin, which also works in an image without `/bin/sh`:

```bash
kubectl --context kind-brokecart -n observability get secret monitoring-grafana \
  -o jsonpath='{.data.admin-password}' | base64 --decode \
  | kubectl --context kind-brokecart -n observability \
      exec -i deployment/monitoring-grafana -c grafana -- \
      grafana cli --homepath /usr/share/grafana \
        --config /etc/grafana/grafana.ini \
        admin reset-admin-password --password-from-stdin
```

The first kubectl reads the Secret locally; the pipe sends decoded input to the CLI, not to the terminal. `exec -i` keeps stdin open. The CLI changes Grafana's persistent user database. That password survives ordinary Pod deletion/recreation while the same PVC/database is retained. A root/admin password recovery operation is different from routine chart configuration.

## Step 2: Loki

```bash
helm upgrade --install loki grafana-community/loki \
  --version 18.16.1 --kube-context kind-brokecart \
  --namespace observability -f infra/platform/loki-values.yaml \
  --wait --timeout 10m

kubectl --context kind-brokecart -n observability \
  get pods,services,pvc -l app.kubernetes.io/instance=loki
```

The local mode is Monolithic/single binary: one Loki process handles ingestion, queries, storage and compaction, backed by a 5Gi filesystem PVC. Replication factor is one. The Nginx gateway supplies a single read/write endpoint. This is not a distributed multi-tenant HA logging installation.

Loki uses TSDB schema v13, filesystem storage and 72h retention with compactor retention enabled. Separate read/write/backend replicas, caches, MinIO, canary and chart tests are disabled to save resources. `auth_enabled: false` means Loki's API has no built-in tenant authentication in this configuration; keep it internal.

Push endpoint:

```text
http://loki-gateway.observability.svc.cluster.local/loki/api/v1/push
```

Grafana data-source base URL is the gateway root, not `/push`:

```text
http://loki-gateway.observability.svc.cluster.local
```

## Step 3: Fluent Bit

```bash
helm upgrade --install fluent-bit fluent/fluent-bit \
  --version 0.58.3 --kube-context kind-brokecart \
  --namespace observability -f infra/platform/fluent-bit-values.yaml \
  --wait --timeout 10m

kubectl --context kind-brokecart -n observability get daemonset fluent-bit
kubectl --context kind-brokecart -n observability \
  logs -l app.kubernetes.io/name=fluent-bit --all-containers --tail=30
```

Why a DaemonSet? A log file on worker 1 is not automatically present on worker 2. Each collector mounts its own node's `/var/log` read-only and tails `/var/log/containers/*.log` using the CRI multiline parser. The Kubernetes filter enriches records with Pod/container/namespace identity and merges JSON application log records.

`/var/lib/fluent-bit` is a node hostPath for tail offsets and disk buffering, not an application PVC. The tail database prevents unnecessarily rereading all old files on every collector restart. Filesystem buffering permits retry while Loki is temporarily unavailable, but the queue is bounded; it is not an unlimited durable log archive.

Output labels are deliberately small: `job`, `cluster`, `namespace`, `pod`, `container`. Arbitrary application labels/annotations are not all promoted to Loki labels. Do not add customer IDs, request IDs or order IDs as labels; keep those as log fields to avoid high cardinality.

## Step 4: Tempo

```bash
helm upgrade --install tempo grafana-community/tempo \
  --version 3.2.0 --kube-context kind-brokecart \
  --namespace observability -f infra/platform/tempo-values.yaml \
  --wait --timeout 10m

kubectl --context kind-brokecart -n observability get pods,pvc \
  -l app.kubernetes.io/instance=tempo
kubectl --context kind-brokecart -n observability logs tempo-0 --tail=30
```

Tempo is one persistent instance with 5Gi local storage, 24h retention, two maximum concurrent queries, a 1Gi container limit and `GOMEMLIMIT=800MiB`. Metrics generation is disabled. Its OTLP ingestion endpoints are 4317/gRPC and 4318/HTTP. Grafana's query API is HTTP port 3200. Do not configure Grafana's data source with the OTLP ingest port.

In the previous Streamflix project, a 1024Mi ballast with a 512Mi memory limit contributed to repeated OOM kills. BrokeCart's Tempo values use a different chart/application baseline and do not carry that ballast setting forward. Verify actual Pod args/resources when diagnosing a similar error rather than blindly copying an old fix.

## Step 5: OpenTelemetry Collector

```bash
helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  --version 0.176.0 --kube-context kind-brokecart \
  --namespace observability -f infra/platform/otel-collector-values.yaml \
  --wait --timeout 10m

kubectl --context kind-brokecart -n observability \
  get deployment,pods,service -l app.kubernetes.io/instance=otel-collector
kubectl --context kind-brokecart -n observability \
  logs deployment/otel-collector --tail=40
```

This is a Deployment collector accepting OTLP at 4317 and 4318. Only the traces pipeline is enabled. Its memory limiter budgets 192Mi with a 48Mi spike allowance inside a 256Mi container; batch processor groups spans before exporting to Tempo with retry/queue behavior. `tls.insecure: true` on the Tempo exporter means plain internal gRPC transport for this hop; it is separate from browser TLS. The local telemetry transport is not end-to-end encrypted.

Java application values send traces to:

```text
http://otel-collector.observability.svc.cluster.local:4318/v1/traces
```

The path `/v1/traces` matters. A healthy collector can still receive no application traffic. `TRACE_SAMPLE_RATE: '0.1'` samples about 10% of traces; generate enough requests or temporarily sample the relevant services at 1.0 for a focused exercise.

## Step 6: Grafana data sources

Prometheus is normally provisioned by kube-prometheus-stack. Loki and Tempo were configured through Grafana UI in this project; the overview dashboard does not automatically create them. Check **Connections → Data sources**:

| Type | URL |
|---|---|
| Prometheus | `http://monitoring-kube-prometheus-prometheus.observability.svc.cluster.local:9090` |
| Loki | `http://loki-gateway.observability.svc.cluster.local` |
| Tempo | `http://tempo.observability.svc.cluster.local:3200` |

These addresses are reached by Grafana's backend inside Kubernetes. They are not URLs to open from a Windows browser. Save/test each data source. If a future chart release changes Service names, use `kubectl -n observability get services` to obtain the actual endpoints.

## Step 7: application dashboards and alerts

Argo deploys `infra/charts/observability-config` into `observability`. That chart creates:

- Dashboard ConfigMap labelled `grafana_dashboard: '1'`, discovered by Grafana's dashboard sidecar.
- PrometheusRule with `release: monitoring`, matching the monitoring release's selectors.

Title: **BrokeCart — application, logs and traces**; UID `brokecart-overview`. Data-source variables avoid assuming the UI-created Loki/Tempo data-source UIDs. Select data sources, namespace(s), Java service(s), time range and log regex.

Every backend's ServiceMonitor also uses `release: monitoring`, selects the backend Service by labels, and scrapes named port `http` at `/actuator/prometheus`. The Operator converts ServiceMonitor declarations into Prometheus scrape configuration. A ServiceMonitor existing in Kubernetes does not prove the selected target is up or that Prometheus's selectors include it.

## Queries to understand the data

Application metric labels use `application="catalog-service"`; the Kubernetes namespace is `brokecart-catalog`.

```promql
sum(rate(http_server_requests_seconds_count{application="catalog-service"}[5m]))
```

Mean HTTP latency is timer sum divided by timer count:

```promql
sum(rate(http_server_requests_seconds_sum{application="catalog-service"}[5m]))
/
sum(rate(http_server_requests_seconds_count{application="catalog-service"}[5m]))
```

No traffic can mean no timer series or a zero denominator. Histogram publication is not enabled, so do not present a p95 query as verified.

```promql
sum(jvm_memory_used_bytes{application="catalog-service",area="heap"})
```

```logql
{cluster="brokecart", namespace="brokecart-catalog"}
```

```logql
{cluster="brokecart", namespace="brokecart-returns"} |= "ERROR"
```

```traceql
{ resource.service.name = "checkout-service" }
```

Use logs to find an error, traces to follow request spans and metrics to see rates/resource trends. The dashboard does not configure automatic trace-ID-to-log correlation; that is an additional exercise.

## Alert meanings

| Rule | Threshold |
|---|---|
| BrokeCartHTTP5xx | 5xx ratio over 5% for 5 minutes, with traffic over 0.1 requests/sec |
| BrokeCartHTTPLatency | Mean latency over 1s for 5 minutes with the same traffic floor |
| BrokeCartDeploymentUnavailable | No available Deployment replicas for 5 minutes |
| BrokeCartPodRestarts | More than three restarts in 15 minutes, sustained for five minutes |

Prometheus evaluates these rules; Alertmanager handles receiver routing. No email/Slack receiver was configured merely by creating the rules. Kafka JMX, Redis, PostgreSQL and Elasticsearch exporters are **not** installed by this chart, and there are no invented outbox/business exporter metrics. Pod/node/container metrics still cover those workloads.

## Verification and common failures

```bash
kubectl --context kind-brokecart -n observability get servicemonitors,prometheusrules
kubectl --context kind-brokecart -n brokecart-catalog get servicemonitor catalog -o yaml
kubectl --context kind-brokecart -n brokecart-catalog get endpointslices
kubectl --context kind-brokecart -n observability get pods,pvc
```

For direct Prometheus target inspection, keep this command running in a separate WSL terminal:

```bash
kubectl --context kind-brokecart -n observability \
  port-forward service/monitoring-kube-prometheus-prometheus 9090:9090
```

Open `http://localhost:9090/targets`. For logs missing in Grafana, inspect Fluent Bit output/retries, Loki readiness and the actual labels before changing the query. For Tempo connection failures, check its Pod's readiness, previous termination reason, Service endpoints and port 3200. See chapter 8 for shared diagnostic commands.
