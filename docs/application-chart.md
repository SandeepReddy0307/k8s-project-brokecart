# Application Helm chart: catalog first

The chart at infra/charts/application supports all 14 HTTP backends. Catalog is the reference service, using infra/values/catalog.yaml and namespace brokecart-catalog. It is not yet a frontend or maintenance-worker chart.

The chart renders catalog and the other service values, including ServiceMonitor, HPA, PDB, network policies and public HTTPRoutes where appropriate. It has not been installed by this step.

## How the Pod receives configuration

| Source | Delivery | Purpose |
|---|---|---|
| catalog-config ConfigMap | envFrom | Port, public origin, Kafka address and trace endpoint |
| catalog-database-credentials Secret | Explicit Secret references | Database name, user and password |
| catalog-application-security Secret | Explicit Secret references | Internal HTTP token and JWT public key |
| catalog-kafka-credentials Secret | Explicit Secret reference | Kafka SASL JAAS configuration |
| catalog-postgres-ca ConfigMap | Read-only /etc/postgres-ca mount | PostgreSQL certificate trust |
| catalog-kafka-config ConfigMap | Read-only /etc/kafka-client mount | Kafka TLS settings and CA |

ESO creates the three credential Secrets from OpenBao. Secret values never appear in the Deployment YAML. ConfigMaps hold public settings and CA certificates.

DB_NAME appears before DB_URL in the environment list. Kubernetes substitutes it into the JDBC URL before starting Java. The URL uses PostgreSQL sslmode=verify-full and the mounted public CA to verify both trust and server hostname.

The Deployment sets KAFKA_ENABLED directly from kafka.enabled. When enabled, it also sets SPRING_CONFIG_ADDITIONAL_LOCATION=file:/etc/kafka-client/kafka.yaml and KAFKA_SASL_JAAS_CONFIG from the Kafka Secret. This keeps the required config file and its mount conditional together. The additional YAML configures SASL_SSL, PLAIN, PEM trust and hostname verification.

Catalog never receives JWT_PRIVATE_KEY. Only an identity deployment with security.identitySigningKey=true includes that reference.

## Deployment and Service

Deployment catalog manages a ReplicaSet. HPA manages the replica count between one and two Pods by default; the Deployment omits replicas while HPA is enabled to avoid competing reconciliation. The Pod uses ServiceAccount catalog; ESO has separate ServiceAccounts for database, application-security and Kafka credential retrieval.

The workload runs as UID/GID 10001, matching its Dockerfile, without an automatic Kubernetes API token. The container root filesystem is read-only; /tmp is a writable emptyDir. The application uses no PVC because its durable state belongs to PostgreSQL and Kafka.

The default request is 100m CPU and 256 MiB RAM, with a 512 MiB memory limit. Java uses up to 65 percent for heap, limits active processor count to two and exits on out-of-memory errors. These are starting values to measure and tune, not a capacity guarantee.

The Deployment keeps three ReplicaSet revisions. Rolling updates allow one extra Pod and zero unavailable Pods; the host needs capacity for that temporary Pod.

Service catalog is ClusterIP port 80, forwarding to the named http port on container port 8080. Its selector matches the Deployment's Pod labels. Other services will use catalog.brokecart-catalog.svc.cluster.local. A public Kong HTTPRoute is still to be configured.

## Health and updates

Startup and liveness check /actuator/health/liveness. Startup allows up to ten minutes before normal probes take over. Readiness checks /actuator/health/readiness, which includes the application's database check. Kafka connectivity is not part of this readiness group and must be verified through functional tests and telemetry.

ConfigMap content checksums in the Pod template trigger a rollout when environment settings or CA/Kafka configuration change. External Secret refresh does not automatically restart a Pod; credential changes require coordinated rollout.

ServiceAccounts, SecretStores and ExternalSecrets have Argo waves -3, -2 and -1 respectively. ConfigMaps/Service are wave 0 and Deployment wave 1. Use the existing custom resource health checks when configuring Argo CD. Waves within this Application do not order PostgreSQL/Kafka Applications; their provisioning and availability must be coordinated in the deployment flow. The process may restart if its database is not available yet.

## Image and delivery status

Application image values initially have a placeholder Docker Hub owner and tag pending-ci until CI updates them. It is not a published, deployable image reference. Confirm the Docker Hub owner and let the per-service CI publish an immutable tag before enabling deployment through Argo CD.

No image was built, pushed or deployed in this step. HPA, PDB, NetworkPolicy and HTTPRoute templates are configured across all backends. VPA is an optional recommendation-only template, disabled until its controller/CRDs exist. See the [deployment runbook](deployment-runbook.md) for activation and live validation.

## Metrics

Catalog enables the optional ServiceMonitor template. It has label release=monitoring, matching the monitoring release's kube-prometheus-stack default selector. Its namespaceSelector looks for Services only in brokecart-catalog, and its label selector matches the catalog Service. Prometheus must itself select ServiceMonitors across application namespaces; that is the pinned monitoring chart's default when the namespace selector is empty. These settings have not been queried from the live cluster in this step.

Prometheus discovers the Service's ready Pod endpoints and scrapes /actuator/prometheus on the named http port every 30 seconds, with a 10-second timeout. The application already exposes this Spring Boot Actuator endpoint and allows internal scraping without a login. Grafana queries the resulting data in Prometheus; it does not scrape the application directly. See the [Prometheus Operator guide](https://prometheus-operator.dev/docs/developer/getting-started/) for the selector relationships.

Logs continue through Fluent Bit to Loki, and traces through the configured OpenTelemetry Collector to Tempo. ServiceMonitor configures metrics only. Network policies must later allow the Prometheus Pods to reach the application port, and public HTTPRoutes must not expose Actuator.

After the application is deployed, check the Prometheus target and use this query in Grafana Explore with its Prometheus data source:

```promql
up{namespace="brokecart-catalog", service="catalog"}
```

A value of 1 means scraping succeeded; 0 means a discovered target failed its scrape. No series can mean the service has no endpoints or the ServiceMonitor was not selected. Actual metric delivery has not been tested because catalog is not deployed yet.

## Local checks

```bash
helm lint infra/charts/application -f infra/values/catalog.yaml
helm template catalog infra/charts/application \
  --namespace brokecart-catalog -f infra/values/catalog.yaml \
  --show-only templates/deployment.yaml
python3 tests/application_chart_configuration.py
python3 tests/application_security_configuration.py
git diff --check
```

On 2026-10-18 rendering/reference checks and offline security-bootstrap tests passed. They verify selectors, Secret keys, ConfigMap mounts, database TLS URL, conditional Kafka delivery, health probes and workload security. These are configuration checks, not a deployed Java application integration test.
