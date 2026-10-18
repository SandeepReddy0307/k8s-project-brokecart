# Verification

Verification performed on 2026-10-14. All listed final checks passed. Results below distinguish application tests from deployment validation.

- Maven reactor `verify`: passed for the common library and all 15 backend artifacts. Tests cover catalog/pricing API validation, quotes, and atomic inbox/domain/outbox rollback and duplicate handling.
- Frontend TypeScript/Vite production build: passed.
- Frontend unit tests: 3 passed.
- Isolated Playwright storefront checks: 4 passed on desktop/mobile. Live API tests are deliberately gated and skipped in the isolated suite.
- Full development-profile API workflow: passed registration/login/roles, authoritative checkout, checkout idempotency, duplicate-event stock protection, cancellation refund/release, payment decline, uncertain provider reconciliation, packing/shipping/delivery, return/refund/restock, ownership checks, notification inbox, reporting, search updates, and cart version protection.

- Full customer/operator Playwright journeys: passed on desktop and mobile (registration, shared cart, purchase, order tracking, cancellation, sign-out/operator sign-in, and operations dashboard).
- Real PostgreSQL/Redis/three-node Kafka/Elasticsearch workflow: purchase, compensation, delayed and uncertain payments, delivery, returns/refunds, notifications, projections, search updates and shared cart protection passed. Poison-event dead-letter delivery, both maintenance tasks, normal-profile exclusion of HTTP relay endpoints, and a purchase with one Kafka node stopped also passed.
- All 15 backend Dockerfiles and the frontend Dockerfile built successfully. Backend runtime checked with a non-root user, read-only root filesystem, dropped capabilities, catalog/readiness and Prometheus responses. Frontend runtime checked for non-root execution, static HTML, health and security headers.

Development-profile tests use H2 and the HTTP relay; real-dependency tests are a separate suite. Screenshots of customer/order and operator screens are under `docs/previews/`.

No Kubernetes, Helm, GitHub Actions, Docker Hub push, Argo CD or observability platform has been installed for this project. Telemetry hooks exist in source; end-to-end collection/export and dashboards remain to be validated with your platform. This is a learning application with a payment simulator, not a production compliance/security certification.
