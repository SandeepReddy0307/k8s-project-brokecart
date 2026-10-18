# BrokeCart observability configuration

The platform components already installed in namespace `observability` perform collection and storage. The `infra/charts/observability-config` chart adds a reproducible application dashboard and alert rules. It does not install another Grafana, Prometheus, Loki, Tempo, or collector. Its Argo CD Application is `brokecart-observability-config` and targets the existing namespace.

## Metrics, logs and traces take different paths

1. Each Java service exposes `/actuator/prometheus`. Its ServiceMonitor tells the existing Prometheus Operator which Service and named HTTP port to scrape. Prometheus collects the metrics every 30 seconds. Grafana queries Prometheus when you open a panel; Grafana is not the metric store.
2. Java writes structured logs to standard output. Kubernetes/containerd stores container logs on each node. The Fluent Bit DaemonSet tails those files and adds Kubernetes metadata. It sends JSON log records to Loki through `loki-gateway`. Grafana reads Loki. The actual Fluent Bit labels are `job`, `cluster`, `namespace`, `pod` and `container`.
3. Micrometer/Spring produces request spans. The app exports them to the OpenTelemetry Collector's HTTP endpoint `/v1/traces`. The collector batches/forwards them to Tempo. Grafana queries Tempo. A running collector alone does not prove that an application is exporting useful spans.

The Prometheus Operator, kube-state-metrics and node-exporter have separate jobs. The Operator reconciles monitoring resources. kube-state-metrics exposes Kubernetes object state, such as desired/available Deployment replicas and Pod restarts. Node-exporter exposes node operating-system metrics. Kubelet/cAdvisor supplies container CPU and memory statistics. Metrics Server serves the resource metrics API used by HPA and `kubectl top`; it is not the store queried by these dashboard panels.

## Dashboard

The chart publishes a ConfigMap labelled `grafana_dashboard: "1"`. The monitoring chart's Grafana dashboard sidecar discovers this label and provisions its JSON file. The dashboard title is **BrokeCart — application, logs and traces** and its stable dashboard UID is `brokecart-overview`.

Choose the metrics, logs and traces data sources using the dashboard's data source selectors. Their Grafana UIDs are not hardcoded because Loki and Tempo were added through the UI. If a selector is empty, configure that data source in Grafana first. These selectors do not create data sources or change their endpoints.

Select one or more BrokeCart namespaces and Java services. All Java services tag their Micrometer meters with `application=${spring.application.name}`, such as `catalog-service`. Namespace names are different: `brokecart-catalog`. The common application's configuration supplies the application tag; Prometheus's scrape configuration supplies Kubernetes labels.

Panels show:

- Business HTTP requests per second and 5xx request rate, excluding health/metrics endpoints.
- **Mean** HTTP latency, calculated from the timer's sum divided by count. Histogram publication is not enabled, so the dashboard does not invent a p95 query.
- JVM heap used and live threads.
- Container CPU and working-set memory, available Deployment replicas, and restarts.
- Loki logs for the selected namespaces, with an optional regular-expression message filter.
- A Tempo TraceQL search using the selected Java service name. Use Grafana Explore with the same Tempo data source to inspect complete traces or refine the query.

For example, a catalog search in Explore uses:

```traceql
{ resource.service.name = "catalog-service" }
```

A corresponding Loki query is:

```logql
{cluster="brokecart", namespace="brokecart-catalog"}
```

Request timers appear after requests have been observed. Idle services can have no business HTTP data. The dashboard uses container metrics independently of the Java-service selector because container metrics have Pod/namespace labels rather than Spring's application tag. The namespace selector controls both.

## Alerts

The PrometheusRule carries `release: monitoring`, matching the existing monitoring release selector.

| Alert | Condition | Meaning |
| --- | --- | --- |
| BrokeCartHTTP5xx | More than 5% 5xx responses for 5 minutes, with more than 0.1 business requests/sec | Sustained backend errors, rather than one isolated failed request |
| BrokeCartHTTPLatency | Mean latency over 1 second for 5 minutes, at the same traffic floor | Slow requests; not a percentile or a contractual SLO |
| BrokeCartDeploymentUnavailable | Zero available Deployment replicas for 5 minutes | Check images, Secrets, Pod events and readiness |
| BrokeCartPodRestarts | More than 3 restarts within 15 minutes, persisting for 5 minutes | Check memory limits, termination reasons and previous logs |

Prometheus evaluates the expressions and sends firing alerts to Alertmanager. Alertmanager routes notifications according to its receiver configuration. Adding rules does not automatically configure an email/Slack receiver. You can inspect firing/pending alerts in Prometheus or Alertmanager before adding external notifications.

These rules describe the Java backends and Kubernetes workloads. Kafka JMX, Redis, Elasticsearch and PostgreSQL exporter metrics are **not** configured by this chart. Application-level outbox counters are also not defined in the current source. There are no fake dependency dashboards or outbox alerts; those require exporters or real application instrumentation first. Pod availability and restart panels still cover those dependency workloads.

## Review and validation

```bash
helm lint infra/charts/observability-config
helm template observability-config infra/charts/observability-config \
  -n observability
python3 tests/observability_configuration.py
```

The four alert expressions also passed promtool check rules using the official Prometheus v3.5.0 image. The checks validate Helm output, dashboard JSON, real Fluent Bit label conventions, dashboard data source references, and alert wiring. They do not demonstrate live end-to-end telemetry. After Argo CD deploys the applications, generate browser/API traffic, verify Prometheus targets, inspect Loki log records, search Tempo for traces, and evaluate the alerts in the actual monitoring stack.

On 2026-10-18, a disposable cached catalog container was started with the explicit local profile, no network access and no external dependencies. After a successful catalogue API request, its actual `/actuator/prometheus` output confirmed `http_server_requests_seconds_count`, `http_server_requests_seconds_sum`, `jvm_memory_used_bytes` and `jvm_threads_live_threads`, including `application="catalog-service"` and HTTP status/URI tags. This verifies the exported metric names; it does not demonstrate collection by the Kubernetes Prometheus instance.

This chart's data ConfigMap contains public dashboard definitions, not passwords or access tokens. Changes to dashboard JSON and alert YAML are reviewed and deployed through Git/Argo CD like application settings.

## Metric naming references

Spring Boot 3.5 documents its automatic `http.server.requests` and JVM meters in the [Actuator metrics reference](https://docs.spring.io/spring-boot/3.5/reference/actuator/metrics.html). Prometheus represents the request timer as `http_server_requests_seconds_count` and `_sum`; JVM heap is `jvm_memory_used_bytes`. Kubernetes object-state names come from the [kube-state-metrics metric documentation](https://github.com/kubernetes/kube-state-metrics/tree/main/docs/metrics). The dashboard does not enable histograms or claim that these series have already been scraped from this deployment.
