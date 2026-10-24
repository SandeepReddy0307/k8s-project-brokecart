# 8. Daily operations, troubleshooting and acceptance tests

[Index](README.md) · [Previous](07-delivery.md) · [Next: file reference](09-file-reference.md)

## After restarting the laptop

1. Start Docker/WSL integration. Check existing kind node containers; do not recreate the cluster just because workloads are not immediately Ready.
2. If the existing node containers are stopped, start those containers. Wait for Kubernetes networking/controllers to recover.
3. Check OpenBao and unseal it with two distinct saved shares if necessary.
4. Confirm SecretStores and ExternalSecrets recover; inspect their actual errors if they do not.
5. Check Argo CD controller/repo-server readiness and Applications. The current HPA cap must stay one on this laptop.
6. Verify browser HTTPS and application API behavior, not only Pods.

```bash
docker ps -a --format '{{.Names}} {{.Status}}'
kind get clusters
kubectl --context kind-brokecart get nodes
kubectl --context kind-brokecart -n kube-system get daemonsets,pods
```

Only if the existing kind node containers are stopped:

```bash
docker start brokecart-control-plane brokecart-worker brokecart-worker2
```

Do not run `kind delete cluster` or delete PVCs as a startup step. OpenBao, application databases and Kafka storage are persistent state worth preserving.

### OpenBao unseal reminder

```bash
kubectl --context kind-brokecart -n openbao exec openbao-0 -- bao status
```

Initialization material is outside the repository at `~/.local/share/brokecart-secrets/openbao-init.json`. Inspect locally, find `unseal_keys_b64`, and run this twice with different keys:

```bash
kubectl --context kind-brokecart -n openbao exec -it openbao-0 -- bao operator unseal
```

Then:

```bash
kubectl --context kind-brokecart -n openbao exec openbao-0 -- bao status
kubectl --context kind-brokecart get secretstores -A
kubectl --context kind-brokecart get externalsecrets -A
```

If `container not found` occurs, the Pod process has not started/recovered yet; it is too early to unseal via exec. Inspect its events/runtime first. Never print or send the initialization file to someone troubleshooting with you.

## A short daily health check

```bash
kubectl --context kind-brokecart get nodes
kubectl --context kind-brokecart get pods -A
kubectl --context kind-brokecart -n argocd get applications
kubectl --context kind-brokecart get hpa -A
kubectl --context kind-brokecart get pvc -A
kubectl --context kind-brokecart get certificates -A
kubectl --context kind-brokecart get httproutes -A
kubectl --context kind-brokecart top nodes
free -h
```

For this baseline, expect one Ready replica for each backend and frontend, three Kafka Pods, healthy single PostgreSQL/Redis/ES instances, one OpenBao Pod, Argo Applications Synced/Healthy and HPAs min/max one. Suspended maintenance CronJobs are intentional. Successful provisioning hooks may already have been deleted.

All kind nodes share host memory. Sum of node “allocatable memory” is not physical capacity. Low `free` memory alone can be cache; look at `available`, swap activity and memory pressure too:

```bash
vmstat 1 5
cat /proc/pressure/memory
cat /proc/pressure/io
kubectl --context kind-brokecart top pods -A --sort-by=memory
```

Old swap usage can remain after pressure subsides; it is active swap-in/out and stalls that indicate current thrashing. Avoid running CI Maven builds and disposable multi-datastore test harnesses during a full-stack load test.

CPU request `100m` means 0.1 CPU for scheduling and the HPA percentage denominator. A Pod using 300m can legitimately show 300% of that request. The backend chart does not impose a CPU limit; `ActiveProcessorCount=1` tunes JVM sizing and is not the same as a hard Kubernetes CPU quota. Memory request affects scheduling, while exceeding the memory limit can terminate the container. More replicas can increase total memory/DB connections even when each replica's CPU percentage falls.

Completed one-shot Job Pods commonly show `0/1 Completed`; they are not meant to remain serving Ready endpoints. Compare the Job's completion count and exit status rather than treating every `0/1` row as a broken long-running service.

### Useful small command details

`kubectl -n` selects a namespace; `--context` selects a cluster/user context; `-o yaml` prints the object; `describe` summarizes status/events; `logs` reads process output; `exec` runs a process inside an existing container. After `--`, arguments belong to the container command. `exec -i` forwards stdin; `-t` allocates a terminal for interactive prompts.

Base64 works on stdin unless a filename argument is supplied. Use public example text to learn it:

```bash
printf '%s' 'hello' | base64
printf '%s' 'aGVsbG8=' | base64 --decode
echo
```

Passing encoded text directly as a positional filename to `base64 -d` causes a “No such file” error. `printf` avoids an unwanted newline becoming part of a password/value. Base64 is encoding, not encryption.

## Browser checks with certificate verification

Export the public CA as shown in chapter 2, then:

```bash
curl --noproxy '*' --cacert /tmp/brokecart-root-ca.crt \
  --resolve brokecart.com:8443:127.0.0.1 -I https://brokecart.com:8443/
curl --noproxy '*' --cacert /tmp/brokecart-root-ca.crt \
  --resolve argocd.brokecart.com:8443:127.0.0.1 -I https://argocd.brokecart.com:8443/
```

Use browser root URLs:

| UI | URL |
|---|---|
| Storefront | https://brokecart.com:8443/ |
| Argo CD | https://argocd.brokecart.com:8443/ |
| Grafana | https://grafana.brokecart.com:8443/ |
| OpenBao | https://openbao.brokecart.com:8443/ui/ |
| Kafka UI | https://kafka.brokecart.com:8443/ |

## Diagnose a service systematically

Choose a real name and inspect before restarting anything:

```bash
service=returns
kubectl --context kind-brokecart -n "brokecart-$service" get deployment,pods,service,endpointslices
kubectl --context kind-brokecart -n "brokecart-$service" describe deployment "$service"
kubectl --context kind-brokecart -n "brokecart-$service" logs "deployment/$service" -c application --tail=80
kubectl --context kind-brokecart -n "brokecart-$service" get events --sort-by=.lastTimestamp
```

For a restarting Pod, use its actual name from `get pods`:

```text
kubectl --context kind-brokecart -n NAMESPACE logs POD -c application --previous --tail=100
kubectl --context kind-brokecart -n NAMESPACE describe pod POD
```

Those last two are command patterns—replace NAMESPACE/POD. Previous logs describe the terminated process; current logs may only show the next startup. An HTTP `connection refused` probe often means the app exited or has not opened its port, not that its probe needs a longer timeout.

| Symptom | First checks |
|---|---|
| Pending | Scheduler events: resources, taints, affinity, PVC binding |
| ContainerCreating | Image pull, volume/certificate/Secret availability, CNI events |
| CreateContainerConfigError | Missing ConfigMap/Secret or missing key |
| ImagePullBackOff | Repository/tag, registry access, rate limits, private pull auth |
| CrashLoopBackOff | Last termination reason and previous application logs |
| OOMKilled | Heap/native memory, container limit and host pressure |
| Running 0/1 | Startup/readiness error; process state alone is insufficient |
| Unknown after restart | Node/containerd/kubelet recovery, not automatically application source failure |
| Service has no usable endpoints | Label selectors and Pod readiness |
| HPA `<unknown>` CPU | Metrics Server, Pod metrics availability and CPU request |

Do not expose metrics/admin/internal APIs publicly just to diagnose them. Use existing RBAC-authorized exec/port-forward carefully.

## Incident recipes from this project

### OpenBao sealed → every SecretStore unhealthy

Evidence: `bao status` reports sealed; ESO events say `503 Vault is sealed`. Unseal first. Existing Kubernetes Secrets may keep already-running applications alive, but refresh/replacement and Argo health can still fail.

If ESO is waiting in retry backoff, trigger a targeted refresh after the provider is valid:

```bash
kubectl --context kind-brokecart -n brokecart-returns annotate externalsecret \
  returns-database-credentials "force-sync=$(date +%s)" --overwrite
```

This annotation requests reconciliation; it does not change the password. A new 403 after unseal is a different problem—inspect bound role account/namespace/audience/policy and TokenReview RBAC.

### `namespace not authorized` from OpenBao

Check the exact SecretStore role, requested ServiceAccount and destination namespace. Role `catalog-secrets` must bind ServiceAccount `catalog-secrets` in `brokecart-catalog`, not in `brokecart-postgres` or the current CLI namespace. Fix the access policy/role using bootstrap scripts, not by weakening all namespace constraints.

### PostgreSQL `53300`: remaining slots reserved for SUPERUSER

Inspect `pg_stat_activity` and `SHOW max_connections` using chapter 5. The previous app default of five connections per Pod plus two replicas across many services exhausted the shared server. The current shared chart overrides maximum pool two/minimum idle one and the local HPA cap is one. Confirm live ConfigMap and Pod template rather than assuming a pushed change has rolled out.

### Elasticsearch Running but never Ready

Check previous/current logs and run `/scripts/check-ready.sh`. The old probe checked a Service that excluded the unready Pod. The fixed probe uses loopback through `--resolve` while keeping certificate hostname checks and authenticated HTTPS. Do not disable TLS/auth to make it pass.

### Argo CD OutOfSync for a long time

```bash
kubectl --context kind-brokecart -n argocd get pods
kubectl --context kind-brokecart -n argocd get application brokecart-catalog \
  -o jsonpath='{.status.operationState.phase}{" | "}{.status.operationState.message}{"\n"}'
kubectl --context kind-brokecart -n argocd logs argocd-application-controller-0 --tail=50
kubectl --context kind-brokecart -n argocd logs deployment/argocd-repo-server --tail=30
```

`Synced` means resources match rendered desired state; `Healthy` means the configured health checks pass. Neither by itself proves a completed business transaction. A Pod may be healthy while an old failed operation blocks the parent's custom health check.

Our controller was repeatedly OOM-killed at 768Mi. The committed Helm platform values now provide a 2Gi limit, Go budget 1536MiB and fewer concurrent processors. If the controller or repo-server is unavailable, application sync cannot apply a ConfigMap even when Git already has the fix.

After fixing the cause, retry only a failed/completed operation, not one that is genuinely progressing:

```bash
kubectl --context kind-brokecart -n argocd patch application brokecart-kafka \
  --type=merge -p '{"operation":{"initiatedBy":{"username":"manual-recovery"},"sync":{}}}'
```

A stale **running** sync to an obsolete revision may need termination before resync. Inspect its revision/tasks first. Prefer the UI's Terminate operation, or deliberately mark that specific operation Terminating; never mass-terminate all healthy hooks. Retrying Kafka reruns topic/ACL provisioning and can take minutes.

### Kafka sync says waiting for provisioning hook

Inspect `logs -f job/kafka-topic-provisioning`. Topics can finish before sequential ACL commands do. Java CLI startup and a 500m CPU limit make this finite work slow. Progressing logs with no failed Pods are different from authentication/network errors. The configured deadline is 900s. A DLT is a retained failed record, not an automatic business replay mechanism.

### Kong `no Route matched`

Kong is reachable but no host/path/listener matched. Check Gateway/HTTPRoute parent conditions, hostname, listener sectionName, path and published configuration. Before application routes exist, this 404 is expected. `curl --resolve` can distinguish DNS errors from routing errors.

### Kong invalid upstream response or refused Admin API

Inspect both Pods separately:

```bash
kubectl --context kind-brokecart -n kong get pods
kubectl --context kind-brokecart -n kong logs deployment/kong-gateway -c proxy --tail=40
kubectl --context kind-brokecart -n kong logs deployment/kong-controller --tail=40
```

A controller unable to connect to gateway Admin API port 8444 can fail while the gateway is restarting. On this laptop host pressure/liveness failures caused that chain; reducing backend replicas allowed both to recover. A public UI HTTP 404 returned by the upstream is different from a Kong-generated route miss or a 502.

For OpenBao's `Client sent an HTTP request to an HTTPS server`, fix the upstream HTTPS Service annotations and verified CA reference from chapter 3. Browser certificate trust does not change Kong's upstream protocol.

### PVC Pending with WaitForFirstConsumer

Check `Used By` and events before assuming the provisioner failed. A standalone claim without a scheduled consumer may remain Pending legitimately. A real Job/Pod that mounts it triggers volume scheduling. In the earlier project a backup PVC kept Helm waiting until a backup consumer Job was created; do not create fake data consumers automatically in this project merely to hide Pending status.

### Local laptop memory pressure

Use `free -h`, `vmstat` and per-Pod metrics. Our current local backend limits total 5.25Gi for 14 × 384Mi, versus 14Gi at 28 × 512Mi. These are limits, not actual memory use, and platform/datastore memory is additional. Backend zero-surge rollouts avoid temporarily doubling all services.

Keep three Kafka nodes unless planning a quorum/topic migration. Keep necessary Argo memory headroom. Prefer one runner, small telemetry volumes and no concurrent full test harness. Lowering memory requests alone changes scheduling, not process usage; lowering limits without heap/native-memory checks can create more OOM loops.

## Pending deployed end-to-end acceptance tests

These are a plan, not completed results. Use fictional users and payment simulation tokens; never real card data. Record order IDs and expected state transitions, screenshots/logs/traces and timestamps.

| Test | Expected evidence |
|---|---|
| Catalog/search page | Products load; search results return from index |
| Register/login/logout | Secure session works; logout clears access |
| Guest-to-user cart merge | Correct items/quantities after login |
| Quote/promotion | Server-calculated cents; BROKE10/shipping rules |
| Approved checkout | One order reaches CONFIRMED, stock reserved/committed, payment captured |
| Repeat idempotency key | Same order; no duplicate charge/order |
| Same key, changed body | Conflict rather than a second order |
| Declined payment | Order fails with inventory compensation |
| Timeout/delayed provider | UNKNOWN attempt reconciles using stable operation ID |
| Insufficient stock | Clear rejection; no captured payment for nonexistent stock |
| Cancel unshipped order | Shipping cancellation, refund and stock release before CANCELLED |
| Ship/deliver | Operator advances state; customer sees tracking/order timeline |
| Return delivered order | Request, operator decision, refund and stock effect |
| Notification/report projections | Corresponding customer inbox and report updates after events |
| Ownership/roles | Customer cannot read another user's records or invoke operator API |
| Telemetry | Matching request metrics, logs and sampled spans in Grafana |
| Maintenance | Each finite task tested manually before unsuspending CronJobs |

For an operator account, use the trusted internal bootstrap endpoint after Identity is Ready. One option is a temporary local-only port-forward in a separate terminal:

```bash
kubectl --context kind-brokecart -n brokecart-identity \
  port-forward service/identity 18083:80
```

The following Python command **creates an operator account**. Run it only when preparing that test; it reads the internal token without printing it and prompts privately for a password:

```bash
python3 - <<'PY'
import base64, getpass, http.client, json, subprocess
encoded = subprocess.check_output([
    'kubectl', '--context', 'kind-brokecart', '-n', 'brokecart-identity',
    'get', 'secret', 'identity-application-security',
    '-o', 'jsonpath={.data.internal-token}'
], text=True)
token = base64.b64decode(encoded).decode()
email = input('Operator email: ').strip()
password = getpass.getpass('Operator password (12+ characters): ')
connection = http.client.HTTPConnection('127.0.0.1', 18083, timeout=20)
connection.request('POST', '/internal/identity/operators',
    body=json.dumps({'email': email, 'password': password}),
    headers={'Content-Type': 'application/json', 'X-Internal-Token': token})
response = connection.getresponse()
print('Operator bootstrap HTTP status:', response.status)
connection.close()
PY
```

Stop the port-forward afterward. Log in through the normal storefront with the chosen account. Do not add an HTTPRoute to `/internal` or store this account's password in Git.

## Automated test layers are different

```bash
bash ./mvnw verify
python3 scripts/ci/validate_infra.py --dependencies
python3 tests/services_configuration.py
python3 tests/gitops_configuration.py
```

These check source and configuration. Frontend tests/build run from `frontend/`. `tests/commerce_flow.py`, `tests/browser_flow.py`, `tests/real_dependencies.py`, Kafka runtime and ES runtime scripts can start disposable processes/containers. Read their setup requirements and memory cost first; they are not automatically tests of this existing deployment. Do not run the full disposable datastore harness alongside the laptop cluster without headroom.

## Backups, restore and deleting resources

PVC retention preserves data through some workload changes; local-path storage, Kafka replicas and an OpenBao PVC are not backups. The repository does not currently automate a complete tested backup/restore system. Before destructive exercises, design/export database backups, OpenBao state/unseal recovery material and Kafka/ES recovery requirements to storage outside the kind node containers, then test restoration in isolation.

Deleting a Helm release, Argo Application, namespace, StatefulSet, PVC or kind cluster has different consequences. Child Applications intentionally lack a cascading deletion finalizer; deleting an Application object does not by itself prove its workload disappeared. Conversely namespace/PVC deletion can destroy data. Inspect ownership and recovery needs before cleanup; never use broad deletion as a readiness fix.
