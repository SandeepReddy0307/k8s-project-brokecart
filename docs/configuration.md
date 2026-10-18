# Configuration and API contracts

## Profiles

Normal mode requires PostgreSQL and valid RSA keys. Use separate databases and restricted database users for each HTTP service. The explicit `local` profile uses H2 and development signing credentials and must never be used for a shared/public deployment.

| Variable | Meaning |
|---|---|
| PORT | Process default from README; all HTTP Dockerfiles set 8080 |
| DB_URL | JDBC PostgreSQL URL for this service's database |
| DB_USER / DB_PASSWORD | Database credentials |
| INTERNAL_TOKEN | Shared internal HTTP token, at least 32 characters |
| PUBLIC_ORIGIN | Exact browser origin, including scheme and non-default port |
| JWT_PUBLIC_KEY | PEM RSA public key, required in normal mode |
| JWT_PRIVATE_KEY | PEM RSA private key, identity only |
| COOKIE_SECURE | Identity cookies default true; false only for explicit HTTP development |
| KAFKA_ENABLED | Defaults true in normal mode; false in local mode |
| KAFKA_BOOTSTRAP_SERVERS | Comma-separated reachable broker addresses |
| REDIS_ENABLED / REDIS_URL | Cart uses Redis in normal mode; URL supports credentials |
| SEARCH_BACKEND | elasticsearch normally; database only for local demonstrations |
| ELASTICSEARCH_URL | Search backend URL |
| ELASTICSEARCH_USERNAME / ELASTICSEARCH_PASSWORD | Elasticsearch authentication; username defaults elastic; supply restricted credentials for deployment |
| TRACE_SAMPLE_RATE | Trace probability, default 0.1 |
| OTEL_EXPORTER_OTLP_TRACES_ENDPOINT | OTLP HTTP trace URL including `/v1/traces` |

Peer URLs use `CATALOG_URL`, `PRICING_URL`, `CART_URL`, `ORDERS_URL`, `PAYMENT_PROVIDER_URL` and the corresponding uppercase service name with hyphens replaced by underscores. Pricing's catalog client uses `CATALOG_BASE_URL`. Defaults point to local process ports; container deployments must override actual dependencies with Kubernetes Service addresses. Environment variables configure applications; Secrets/ConfigMaps are yours to write.

Kafka's baseline is PLAINTEXT for local learning. Supply Spring Kafka security properties for TLS/SASL when you implement them. JDBC/Redis/Elasticsearch transport security is similarly configured through their connection settings; this source does not provision certificates.

The maintenance worker requires `INTERNAL_TOKEN`, `TASK=expire-reservations` with `INVENTORY_URL`, or `TASK=reconcile-payments` with `PAYMENTS_URL`. It exits after one invocation.

## Browser API routing

Preserve paths when routing. Operator endpoints require an OPERATOR JWT, and customer resources enforce ownership.

| Prefix | Backend |
|---|---|
| /api/catalog | catalog |
| /api/pricing | pricing |
| /api/identity | identity |
| /api/cart | cart |
| /api/checkout | checkout |
| /api/orders, /api/operations/orders | orders |
| /api/operations/inventory | inventory |
| /api/operations/payments | payments |
| /api/shipping, /api/operations/shipping | shipping |
| /api/returns, /api/operations/returns | returns |
| /api/notifications | notifications |
| /api/search | search |
| /api/operations/reports | reporting |

Payment-provider and maintenance/internal routes have no public browser route. Do not expose `/internal/...` through the public Gateway.

Important operations:

- `POST /api/identity/register` and `/login`: `{email,password}`; passwords 12–128 characters, subject to BCrypt’s 72-byte UTF-8 input limit. Login sets an HttpOnly session cookie. `GET /me` returns user/roles; `POST /logout` clears the cookie.
- `GET /api/catalog/products`: browsing/filter/pagination. `GET /api/catalog/products/{id}` gets a product. Operator `POST .../{id}/price`: `{priceCents}`.
- `POST /api/pricing/quotes`: `{items:[{productId,quantity}],promoCode}`. Prices and totals are calculated server-side in cents.
- `GET /api/cart`; `PUT /api/cart/items/{id}`: `{quantity}` from 0 to 10, where 0 removes the item.
- `POST /api/checkout`: `Idempotency-Key` header (8–80 characters) and `{address,paymentToken,promoCode}`. Repeating a key/body returns the same order; changing the body gives 409. Tokens: `tok_approved`, `tok_declined`, `tok_timeout`, `tok_delayed`.
- `GET /api/orders` and `/{id}`; `POST /{id}/cancel` for a confirmed order.
- `GET /api/shipping/orders/{id}`. Operator `POST /api/operations/shipping/{id}/advance`: READY → PACKED → SHIPPED → DELIVERED.
- `POST /api/returns`: `{orderId,reason}` for a delivered order. Operator `POST /api/operations/returns/{orderId}/approve` or `/reject`.
- `GET /api/notifications`; `POST /api/notifications/{id}/read`.
- `GET /api/search/products?q=...`; operator `GET /api/operations/reports`.
- Operator `GET /api/operations/inventory`; `POST /api/operations/inventory/{productId}/restock`: `{quantity}`.

Internal operator bootstrap is `POST /internal/identity/operators` with `{email,password}` and `X-Internal-Token`. Use it from a trusted environment, not the public frontend. Internal maintenance endpoints are `/internal/inventory/expire` and `/internal/payments/reconcile`.

All services expose actuator health/probe and Prometheus endpoints. The frontend container exposes `/health`. Restrict metrics access in your infrastructure. Application readiness checks DB connectivity; additional dependency alerts remain necessary.
