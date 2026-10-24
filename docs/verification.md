# Verification

## Earlier isolated application checks: 2026-10-14

All checks listed in this historical section passed. These results describe isolated application/dependency fixtures, not the later deployed cluster acceptance test.

- Maven reactor `verify`: passed for the common library and all 15 backend artifacts. Tests cover catalog/pricing API validation, quotes, and atomic inbox/domain/outbox rollback and duplicate handling.
- Frontend TypeScript/Vite production build: passed.
- Frontend unit tests: 3 passed.
- Isolated Playwright storefront checks: 4 passed on desktop/mobile. Live API tests are deliberately gated and skipped in the isolated suite.
- Full development-profile API workflow: passed registration/login/roles, authoritative checkout, checkout idempotency, duplicate-event stock protection, cancellation refund/release, payment decline, uncertain provider reconciliation, packing/shipping/delivery, return/refund/restock, ownership checks, notification inbox, reporting, search updates, and cart version protection.

- Full customer/operator Playwright journeys: passed on desktop and mobile (registration, shared cart, purchase, order tracking, cancellation, sign-out/operator sign-in, and operations dashboard).
- Real PostgreSQL/Redis/three-node Kafka/Elasticsearch workflow: purchase, compensation, delayed and uncertain payments, delivery, returns/refunds, notifications, projections, search updates and shared cart protection passed. Poison-event dead-letter delivery, both maintenance tasks, normal-profile exclusion of HTTP relay endpoints, and a purchase with one Kafka node stopped also passed.
- All 15 backend Dockerfiles and the frontend Dockerfile built successfully. Backend runtime checked with a non-root user, read-only root filesystem, dropped capabilities, catalog/readiness and Prometheus responses. Frontend runtime checked for non-root execution, static HTML, health and security headers.

Development-profile tests use H2 and the HTTP relay; real-dependency tests are a separate suite. Screenshots of customer/order and operator screens are under `docs/previews/`.

At the time of those 2026-10-14 checks, the later Kubernetes delivery platform had not yet been installed. That historical state has changed; see the deployment snapshot below. This is a learning application with a payment simulator, not a production compliance/security certification.


## Deployed infrastructure snapshot: 2026-10-24

During the recovery session, live read-only checks confirmed all 23 Argo CD Applications Synced/Healthy, no unready Pods, all 14 HTTP backends at one desired/Ready replica with HPA min/max one, 384Mi backend memory limits and zero rollout surge. Kong gateway/controller were Ready. Public-CA-verified HTTPS returned 200 for storefront `/` and Argo CD `/`; direct Argo CD `/applications` returned 404. PostgreSQL had 34 active/idle/background connections in total at the measurement. WSL had about 2.9Gi memory available. These are point-in-time observations.

The one-replica resource-saving configuration is commit `26ec828`. The recovery directly capped live HPAs/Deployments to the same committed desired state, refreshed failed ExternalSecrets after OpenBao unseal and allowed Argo to complete reconciliation.

**Pending:** the user's full customer/operator shopping acceptance journey on this deployed kind cluster, including payment uncertainty, compensation, delivery, return, ownership and telemetry correlation. Do not label it completed based on healthy Pods. Follow the [operations and acceptance checklist](handbook/08-operations.md).
