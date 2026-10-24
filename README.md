# BrokeCart

**Full cart, empty wallet.** A runnable shopping application for learning distributed commerce on a local kind cluster.

**Start with the [complete end-to-end handbook](docs/handbook/README.md): cluster setup, every platform component, every service, files, commands, CI/CD, security, observability and troubleshooting.**

The local deployment was verified Synced/Healthy on 2026-10-24 with all backends at one replica and HPA min/max one. The deployed shopping journey remains a separate acceptance test; infrastructure readiness does not certify business correctness.

The repository contains the application source, Maven builds, Dockerfiles, Helm charts, selective GitHub Actions workflows and Argo CD definitions for the local kind learning environment. Follow the [deployment runbook](docs/deployment-runbook.md) to review and activate them using your GitHub Environment and local self-hosted runner. Definitions in Git do not deploy the stack until the delivery flow is activated.

## Applications

| Application | Default process port | Responsibility |
|---|---:|---|
| catalog-service | 8081 | Product catalog, authoritative prices, catalog change events |
| pricing-service | 8082 | Server-side quotes, BROKE10 discount, shipping calculation |
| identity-service | 8083 | Registration, BCrypt passwords, signed JWT sessions, operator roles |
| cart-service | 8084 | Shared Redis carts, atomic quantity changes, version-safe checkout clearing |
| checkout-service | 8085 | Cart and quote coordination, idempotent checkout |
| orders-service | 8086 | Persisted order state machine and compensating purchase saga |
| inventory-service | 8087 | Stock reservations, commits, releases, restocking, expiry requests |
| payments-service | 8088 | Authorization, capture, void, refund, uncertain-result reconciliation |
| payment-provider-service | 8089 | Persistent, idempotent **simulated** payment provider |
| shipping-service | 8090 | Packing, shipment, delivery, tracking and cancellation |
| returns-service | 8091 | Delivered-order returns, operator approval and refunds |
| notifications-service | 8092 | Persisted customer notification inbox |
| search-service | 8093 | Elasticsearch product index and search |
| reporting-service | 8094 | Event-derived operator sales/order reports |
| maintenance-worker | none | One-shot reservation expiry or payment reconciliation task |
| frontend | 5173 development / 8080 container | Responsive React storefront, account, checkout, orders and operator console |

All HTTP backends use Java 17, Spring Boot and Maven. Each owns its database; shared Java code supplies security, persistence, telemetry and event delivery, not a shared commerce database. Normal mode uses PostgreSQL, Redis, Kafka and Elasticsearch. Eight original product illustrations ship with the UI.

## Run application-only development

Install JDK 17, Python 3, Node.js >=22.12 and npm. From this directory:

```bash
./mvnw verify
python3 tools/run-local.py
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. Startup launches the services in small batches; allow a few minutes. Ctrl+C stops them. Logs are written to the displayed temporary directory.

This explicit development profile uses temporary H2 databases, SQL cart storage, development signing keys and an HTTP event relay. Data resets when processes stop. It is a way to learn the application before you provide infrastructure, not a Kafka/Redis deployment.

To enable the operator console, set `BROKECART_OPERATOR_PASSWORD` to a chosen password of at least 12 characters before starting the launcher. Sign in as `operator@brokecart.local`. Customer accounts are created through the UI. The operator console can pack/ship/deliver orders, review returns, restock inventory, change prices and view reports/payment attempts.

Payments accept only simulation choices: approved, declined, timeout and delayed. Never enter actual card information. Money is integer USD cents; BROKE10 takes 10% off, rounded down. Shipping is $4.99 below a discounted subtotal of $100, otherwise free.

## Build images

Run backend builds from the repository root (the context must include `libraries/`):

```bash
docker build -f services/catalog-service/Dockerfile -t YOUR_DOCKERHUB_USER/brokecart-catalog:local .
docker build -f services/orders-service/Dockerfile -t YOUR_DOCKERHUB_USER/brokecart-orders:local .
docker build -f services/maintenance-worker/Dockerfile -t YOUR_DOCKERHUB_USER/brokecart-maintenance:local .
docker build -t YOUR_DOCKERHUB_USER/brokecart-frontend:local frontend
```

Each service directory has its own Dockerfile. The identical Maven build stage can be cached across backend builds. Runtime images run as a non-root user; HTTP containers listen on port 8080. The frontend container serves static files; your Gateway must route `/api/...` to the corresponding backend, preserving the path. There is no application API-gateway service: your Kubernetes Gateway will provide the entry point.

## Tests

```bash
./mvnw verify
python3 tests/commerce_flow.py
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

For real customer and operator browser journeys, build JARs first, then run `python3 tests/browser_flow.py` from the root. Install Playwright Chromium first; this test uses the normal browser cache unless you set `PLAYWRIGHT_BROWSERS_PATH`.

`tests/commerce_flow.py` starts isolated development processes and exercises purchase, cancellation, decline, provider reconciliation, delivery, returns, ownership checks, search updates and reporting.

From the root, `python3 tests/real_dependencies.py` runs those contracts against disposable Docker PostgreSQL/Redis/Elasticsearch and a three-node Kafka quorum, then checks a purchase with one Kafka node stopped. It downloads images if necessary and needs several GB of memory. It removes only its own labelled fixtures. This is a test harness, not your deployment setup.

Read [architecture](docs/architecture.md), [configuration](docs/configuration.md), and [verification](docs/verification.md) before writing the deployment.

Kafka infrastructure configuration, secret bootstrap, read-only Kafka UI, and verification are documented in [Kafka setup](docs/kafka-setup.md). Elasticsearch persistence, TLS and search-user provisioning are documented in [Elasticsearch setup](docs/elasticsearch-setup.md). These charts are deployed by Argo CD; building application images alone does not install Kubernetes resources.

## Scope and limits

This is a production-style learning application, not an audited production retail platform. Payment settlement is simulated, notifications are an in-app inbox, shipping is operator-driven, returns cover whole orders, and seed products are fictional. Tax, real carriers, email/SMS delivery, MFA, password recovery, key rotation, DLT replay tooling and regulatory compliance are not implemented. Lists/projections currently cap scans at 1,000 records and need pagination for larger workloads. Operational security, backups, retention, availability and resource sizing belong to the infrastructure you will build.
