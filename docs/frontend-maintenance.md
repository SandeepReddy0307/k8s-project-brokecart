# Storefront, public routing, and scheduled maintenance

The frontend chart runs the existing React production build using its unprivileged Nginx image on port 8080. A ClusterIP Service exposes port 80 internally. Kong's HTTPS listener accepts `brokecart.com` and routes `/` to that Service. More specific backend `/api/...` HTTPRoutes take precedence. Paths are preserved: no prefix stripping or authentication plugin changes the application's JWT cookie flow. Backend application security remains responsible for customer and operator authorization. The payment-provider simulator has no public route.

The frontend gets no database passwords, internal token, Kubernetes API token, or JWT signing key. Its `/health` endpoint supplies readiness/liveness checks. There is no Prometheus endpoint in this Nginx image, so no frontend ServiceMonitor is created. Logs go to stdout/stderr and the existing Fluent Bit pipeline. The root filesystem is read-only, with a bounded writable `/tmp`. One replica keeps the local memory footprint small. Optional HPA/PDB settings allow a later availability exercise; a PDB with one minimum available replica can block node drains when only one replica exists.

`infra/values/frontend.yaml` holds its image reference. CI replaces the placeholder repository/tag before Argo CD deployment. To inspect it:

```bash
helm lint infra/charts/frontend -f infra/values/frontend.yaml
helm template frontend infra/charts/frontend -n brokecart-frontend -f infra/values/frontend.yaml
```

The maintenance chart runs the existing `maintenance-worker` Java application as two bounded CronJobs in `brokecart-maintenance`: `expire-reservations` calls inventory's internal expiry endpoint; `reconcile-payments` calls payments' internal reconciliation endpoint. Both run every five minutes in UTC, with overlapping executions prohibited, a two-minute job deadline, two retries, and limited Job history. They have no Service because they make outbound requests and then exit. No HPA or ServiceMonitor applies to these short-lived tasks.

The Jobs read only the internal service token from a namespaced Secret created by External Secrets. The `maintenance-application-secrets` identity authenticates to OpenBao and its policy permits reading `brokecart/shared/internal` only. The workload identity `maintenance` has no API permissions and receives no mounted Kubernetes API token. The internal token is still a shared application credential, not a replacement for NetworkPolicy or mutual TLS.

Both schedules are **suspended initially**. After deploying dependencies and validating application behavior, change `tasks.<task>.suspend` to `false` in `infra/values/maintenance.yaml`, commit, and let Argo CD reconcile. A manual run for validation can be created from the CronJob after deployment:

```bash
kubectl --context kind-brokecart -n brokecart-maintenance create job --from=cronjob/maintenance-expire-reservations maintenance-expiry-check
kubectl --context kind-brokecart -n brokecart-maintenance logs job/maintenance-expiry-check
```

Helm rendering verifies configuration; it does not demonstrate that live peers accept the token or that business reconciliation succeeds. Those checks belong to deployment testing. No browser route exposes `/internal` or `/actuator` on a backend.
