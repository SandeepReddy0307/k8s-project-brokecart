# Application architecture

## Request and purchase flow

The browser makes same-origin `/api` requests through your future Gateway. Registration/login goes to identity. Catalog supplies products; search uses an Elasticsearch projection. Pricing always fetches current catalog prices, so browser prices are never trusted. Authenticated cart mutations go to Redis; guest carts are browser-local and merge on login.

Checkout reads the customer's server cart, requests a server quote, and creates an order using an idempotency key. It consumes the cart only if its version still matches, preserving changes made in another tab. An order stores price/address snapshots and starts in RESERVING.

```mermaid
sequenceDiagram
    participant Browser
    participant Checkout
    participant Orders
    participant Inventory
    participant Payments
    participant Provider
    participant Shipping
    Browser->>Checkout: Checkout with idempotency key
    Checkout->>Orders: Create priced order
    Orders-->>Inventory: inventory.reserve via Kafka
    Inventory-->>Orders: inventory.reserved
    Orders-->>Payments: payment.authorize
    Payments->>Provider: Idempotent authorization
    Payments-->>Orders: payment.authorized
    Orders-->>Shipping: shipping.accept
    Shipping-->>Orders: shipping.accepted
    Orders-->>Payments: payment.capture
    Payments->>Provider: Idempotent capture
    Payments-->>Orders: payment.captured
    Orders-->>Inventory: order.confirmed
    Browser->>Orders: Read confirmed order
```

Inventory reserves stock with row locks and validates all lines before reducing availability. A declined authorization releases stock. Failed fulfillment voids the authorization and releases stock. A confirmed cancellation asks shipping first, then refunds the captured payment and releases inventory; the order becomes CANCELLED only after both compensations finish. Shipping rejects cancellation once shipped. A delivered order can be returned: operator approval triggers a refund, then stock restoration and RETURNED state.

A provider timeout is an uncertain outcome, not a decline. Payments stores a stable operation ID and reconciles the provider result rather than creating another authorization. The provider simulator deliberately supports delayed/timeout outcomes to make this behavior observable.

Expired reservations request a decision from orders; orders serializes that decision against authorization/fulfillment transitions. Inventory does not release stock merely because a remote status check was stale.

## Durable event delivery

Domain changes and outbound events commit in the same database transaction. A scheduled publisher locks a per-database mutex and publishes ordered outbox records with Kafka `acks=all`. The record key is the aggregate ID. A crash between Kafka publication and marking the row can redeliver; a consumer's inbox ID and domain mutation commit together, making repeated delivery safe. This is at-least-once delivery with deduplication, not a claim of global exactly-once execution.

Each service has a separate consumer group. Retries precede a `.DLT` destination; offset acknowledgment follows successful handling or successful DLT publication. You will provision topics and design DLT monitoring/replay. Topic partition count and replication are infrastructure settings.

| Topic | Consumers |
|---|---|
| catalog.events | search |
| inventory.commands | inventory |
| inventory.events | orders |
| payments.commands | payments |
| payments.events | orders, returns |
| shipping.commands | shipping |
| shipping.events | orders, notifications |
| orders.events | inventory, notifications, reporting |
| returns.events | orders, notifications |

Each topic also needs `<topic>.DLT` with matching partitions. Event JSON carries `eventId`, `eventType`, `schemaVersion`, `aggregateId`, `correlationId`, `causationId`, `occurredAt` and `payload`. Current schema version is 1. Topics contain customer/order information; restrict access and set retention deliberately.

## Data and trust boundaries

Identity owns password hashes/accounts. Cart owns Redis keys. Orders owns the purchase snapshot/timeline. Inventory owns stock/reservations; payments owns attempts/reconciliation; the simulator owns financial operation results. Shipping, returns and notifications own their records. Reporting and search are rebuildable projections. Common JDBC document storage supports transactions and locks; catalog additionally uses JPA/Flyway for its product table. Flyway creates schemas at startup; you decide whether to isolate migrations into deployment Jobs later.

Identity signs JWTs using a private RSA key; other services verify with the public key. Ownership checks protect customer orders/returns/notifications, and operator endpoints require OPERATOR. Internal HTTP calls require a shared token of at least 32 characters. Browser sessions are HttpOnly cookies with SameSite=Strict and secure cookies by default; unsafe cookie requests validate Origin. TLS termination and workload access policies are your infrastructure responsibilities.

## Telemetry and deployment boundaries

Services expose `/actuator/prometheus`, `/actuator/health/liveness` and `/actuator/health/readiness`; readiness currently includes database connectivity. It does not guarantee Kafka, Redis or Elasticsearch health. Structured JSON logs go to stdout. Micrometer provides HTTP/Kafka observations and OTLP trace export. You will install Prometheus, a log collector/Loki, a trace collector/Tempo and Grafana, then wire endpoints and dashboards.

The maintenance worker is one-shot application code suitable for a future Kubernetes Job/CronJob. HTTP services suit Deployments; databases/brokers suit your StatefulSets/PVCs. ServiceAccounts, Secrets, ConfigMaps, certificates, Gateway routes, PDBs, HPAs, VPAs and network policies are intentionally left for you to author. The application does not call the Kubernetes API.
