# Service configuration and dependency map

All 14 HTTP backends use `infra/charts/application`, with one Helm release and namespace per service. For example, release `catalog` in namespace `brokecart-catalog` uses `infra/values/catalog.yaml`. This avoids maintaining 14 copies of the same Deployment template.

Every backend receives its own PostgreSQL database username/password/database through an ExternalSecret. Its application security Secret contains the shared internal-service token and JWT public key. Only identity receives the JWT private signing key. External Secrets uses separate, narrowly bound OpenBao service accounts for database, application security, and optional Kafka/Redis/Elasticsearch credentials; the running application service account does not mount a Kubernetes API token.

| Service | Main responsibility | Direct HTTP dependencies used by its code | Event use | Extra dependency |
| --- | --- | --- | --- | --- |
| catalog | Product catalogue, prices and product change publication | None | Publishes catalogue events | PostgreSQL |
| pricing | Calculate quotes and promotions | catalog | None | PostgreSQL |
| identity | Registration, login, JWT sessions and operator creation | None | None | PostgreSQL; private signing key |
| cart | Store customer carts, validate products and consume checked-out carts | catalog | None | PostgreSQL and Redis |
| checkout | Coordinate cart snapshot, quote and order creation | cart, pricing, orders | None | PostgreSQL |
| orders | Order lifecycle and saga coordination | None | Publishes commands/events; consumes stock, payment, shipping and return events | PostgreSQL |
| inventory | Reserve/release stock and expire reservations | orders | Consumes inventory commands/orders; publishes inventory events | PostgreSQL |
| payments | Payment operations and reconciliation | payment-provider | Consumes payment commands; publishes payment events | PostgreSQL |
| payment-provider | Simulated external payment processor | None | None | PostgreSQL; internal HTTP only |
| shipping | Shipments and delivery updates | orders | Consumes shipping commands; publishes shipping events | PostgreSQL |
| returns | Return review, refunds and restocking | orders | Consumes payments; publishes return events and payment/inventory commands | PostgreSQL |
| notifications | Project customer notifications | None | Consumes order, shipping and return events | PostgreSQL |
| search | Search product projection and reindex reconciliation | catalog | Consumes catalogue events | PostgreSQL and Elasticsearch |
| reporting | Operator order/sales projection | None | Consumes order events | PostgreSQL |

See the application's architecture documentation for business operations and the Kafka setup document for exact topic ACLs. Values include every peer URL understood by the shared service configuration; the table shows the subset actually called by current code. A configured URL does not mean every service calls every other service.

## How a peer address works

Inside a Pod, `http://orders.brokecart-orders.svc.cluster.local` resolves to the orders Service in its own namespace. Kubernetes Service port 80 forwards to container port 8080. The Service tracks ready Pods, so consumers do not store Pod IPs. These URLs use internal HTTP and application authentication; they are not an assertion of service-mesh mutual TLS.

Pricing uses `CATALOG_BASE_URL` in addition to the shared `CATALOG_URL`. Supplying both avoids accidentally calling the application's localhost development fallback. Every backend listens on 8080 in Kubernetes even though local development uses distinct ports.

The browser calls the Kong HTTPS Gateway at `https://brokecart.com:8443`. Public HTTPRoutes preserve the application's `/api/...` paths. They do not expose `/internal` or `/actuator`, and payment-provider has no public HTTPRoute. The Java services enforce JWT roles themselves; enabling Kong auth plugins is a separate security decision and must not remove backend authorization.

## Secrets and TLS

The Git values contain OpenBao paths and Kubernetes Secret names, not passwords. The database Secret keys are `username`, `password` and `database`. Kafka's ExternalSecret builds the SASL login configuration from its scoped username/password; Kafka's client configuration verifies its TLS hostname against the public local CA.

Only cart enables Redis. It reads `brokecart/redis/auth` via OpenBao role `cart-redis-secrets`, then composes an authenticated Redis URL at Pod startup. The current Redis chart uses authenticated plain TCP within the cluster; this is not Redis TLS.

Only search enables Elasticsearch. It reads `brokecart/search/elasticsearch` using role `search-elasticsearch-secrets` and calls `https://elasticsearch.brokecart-elasticsearch.svc.cluster.local:9200`. The JVM trust configuration imports the public local CA into a truststore while retaining standard Java certificate authorities. Hostname verification stays enabled. Truststore files contain public certificates, so their `changeit` password is not an application credential.

Changing OpenBao credentials does not automatically restart Pods whose credentials are environment variables. Coordinate database/Kafka credential rotation with the server and application rollout; do not regenerate passwords blindly. Certificate trust and CA replacement also need a planned rollout.

## Scaling and observability

Each backend starts at one replica for the local machine. HPA can scale it to two based on 70% requested CPU utilization; the Metrics Server supplies CPU metrics, and requests give the percentage its denominator. A PodDisruptionBudget with `maxUnavailable: 1` permits maintenance of a single-replica local service but cannot promise continuous availability at that replica count. Kafka consumers have at most three active consumers per topic group with the current three partitions. No VPA component is assumed installed; its optional recommendation-only configuration stays disabled until its controller and CRDs exist.

Prometheus scrapes each backend's `/actuator/prometheus` through a ServiceMonitor. Structured console logs go to Fluent Bit, then Loki. Spring/Micrometer traces are exported to the OpenTelemetry Collector's HTTP `/v1/traces` endpoint, then Tempo. Grafana reads Prometheus, Loki and Tempo. `TRACE_SAMPLE_RATE: "1.0"` intentionally samples every request for this local learning environment; adjust volume and sampling when needed.

## Images and automated deployment

Repository and tag values initially contain `replace-with-your-dockerhub-user` and `pending-ci`. They are placeholders, not deployable image references. GitHub Actions uses the GitHub Environment's `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` to publish images and writes the concrete repository and immutable commit tag into GitOps values. Argo CD then reconciles the desired state. No Docker Hub token belongs in Git or Helm values.

To review one service without deploying it:

```bash
helm lint infra/charts/application -f infra/values/orders.yaml
helm template orders infra/charts/application \
  --namespace brokecart-orders -f infra/values/orders.yaml
```

A successful render verifies template configuration; it does not prove image availability, OpenBao authorization, successful database migration, or live delivery of metrics/events/traces. Those require the deployment and end-to-end validation stages.
