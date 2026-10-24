# 7. Helm, Docker, selective CI and Argo CD

[Index](README.md) · [Previous](06-services.md) · [Next: operations](08-operations.md)

## Helm explained through Catalog

A chart is a directory/package containing templates and default values. A values file supplies inputs. Rendering combines them into Kubernetes YAML. A traditional Helm release records a chart installation/upgrade and its revision history in Kubernetes. None of these is the same as a Docker image.

For Catalog:

```text
infra/charts/application/Chart.yaml       chart name/version
infra/charts/application/values.yaml      shared defaults
infra/values/catalog.yaml                Catalog overrides
infra/charts/application/templates/      Kubernetes resource templates
infra/argocd/applications/catalog.yaml    Argo source, chart, values, namespace
```

Helm merges maps: Catalog's `config` entries extend shared pool defaults rather than discarding that entire map. Scalar overrides replace earlier values; lists are generally replaced, not merged item by item. Later `-f` files and explicit overrides have higher precedence. Keep the intended final inputs visible when debugging.

### Read these template expressions

| Expression | Meaning |
|---|---|
| `{{ .Values.database.secretName }}` | Read that value from the merged inputs |
| `{{ .Release.Namespace }}` | The rendering/install target namespace |
| `{{ .Release.Name }}` | Catalog's logical release name, `catalog` |
| `{{ ... \| quote }}` | Output a YAML string safely; not encryption/base64 |
| `nindent 12` | Add a newline and indent 12 spaces to nest YAML correctly |
| `toYaml` | Serialize a values object as YAML |
| `if`, `range` | Conditionally render or repeat template content |
| `required`, `fail` | Reject missing/invalid inputs during rendering |
| `.Files.Get` | Read packaged chart files such as a public CA or script |
| `b64enc` | Encode public CA text for a field expecting base64 |
| `sha256sum` in annotations | Change the Pod template when config text changes |

Helm expressions disappear from the generated manifest. Kubernetes receives ordinary values, not `.Values` placeholders. Inspect rendered output to separate Helm/YAML issues from cluster runtime issues.

```bash
cat infra/charts/application/Chart.yaml
cat infra/charts/application/values.yaml
cat infra/values/catalog.yaml
helm lint infra/charts/application -f infra/values/catalog.yaml
helm template catalog infra/charts/application -n brokecart-catalog \
  -f infra/values/catalog.yaml > /tmp/catalog-rendered.yaml
```

## Platform Helm releases versus Argo-rendered charts

Platform components were installed with Helm CLI:

```bash
helm list --kube-context kind-brokecart -A
helm list --all --kube-context kind-brokecart -n argocd
helm status argocd --kube-context kind-brokecart -n argocd
helm history argocd --kube-context kind-brokecart -n argocd
helm get values argocd --kube-context kind-brokecart -n argocd
helm get values argocd --all --kube-context kind-brokecart -n argocd
helm get manifest argocd --kube-context kind-brokecart -n argocd
```

`get values` returns explicit overrides; `--all` includes computed/default values. A values/manifest dump can contain sensitive inline configuration from other charts; do not indiscriminately publish it. Our application passwords are provider references rather than literal chart values.

To inspect a downloaded chart locally:

```bash
helm search repo argo/argo-cd --versions
helm show chart argo/argo-cd --version 10.10.5
helm show values argo/argo-cd --version 10.10.5 > /tmp/argo-default-values.yaml
helm pull argo/argo-cd --version 10.10.5 --untar --untardir /tmp/brokecart-chart-review
```

`helm upgrade --install` installs if the release does not exist; otherwise it computes/applies an upgrade and increments its revision. `--wait` waits for supported resource readiness; `--timeout` bounds that wait. `--atomic` can roll back/uninstall on failure, which previously made a failing install disappear. Do not add it blindly while learning an uninitialized OpenBao or delayed PVC workflow.

For a **platform** rollback, inspect history and choose a known-good revision:

```text
helm rollback RELEASE GOOD_REVISION --kube-context kind-brokecart -n NAMESPACE --wait --timeout 10m
```

The line above is a syntax pattern, not a literal command. For Argo CD, the old 768Mi controller limit was known to fail; do not roll back to that configuration just because it has a smaller revision number.

The application charts are rendered by Argo CD and applied by Argo—not installed as Helm CLI releases. Thus no `helm status catalog`/`helm rollback catalog` is expected. Inspect Catalog's Application, values and live resources; use Git to change/revert its desired state.

## Source builds and Docker images

The root `pom.xml` is a Maven multi-module reactor: shared `commerce-common`, 14 HTTP modules and maintenance worker. `-pl` selects a module; `-am` also builds its dependencies. `verify` runs the Maven build/test lifecycle. Building a JAR is different from building/pushing an image.

```bash
bash ./mvnw --batch-mode -pl services/catalog-service -am verify
```

Every backend Dockerfile has two stages:

1. Maven/JDK build stage copies the root reactor, libraries and services; BuildKit cache holds Maven dependencies. It packages only the selected module and dependencies. Docker's package step skips tests because CI already ran the test gate.
2. JRE runtime stage receives only the JAR, creates non-root UID/GID 10001 and runs `java -jar /app/app.jar` on 8080.

```bash
docker build -f services/catalog-service/Dockerfile \
  -t YOUR_DOCKERHUB_USER/brokecart-catalog:local .
docker build -f services/maintenance-worker/Dockerfile \
  -t YOUR_DOCKERHUB_USER/brokecart-maintenance:local .
docker build -t YOUR_DOCKERHUB_USER/brokecart-frontend:local frontend
```

Replace `YOUR_DOCKERHUB_USER`; these examples build local images only. Backend build context must be the repository root so `libraries/` exists. Frontend context is `frontend/`: Node/npm builds static assets, and the final Nginx image does not need the Node compiler/runtime to serve them.

The Deployment's `JAVA_TOOL_OPTIONS` overrides the image default, allowing the smaller local JVM budget without rebuilding source/images. Changing code requires a new build; changing a ConfigMap/Pod resource value normally does not.

## GitHub Environment and self-hosted runner

Repository: `SandeepReddy0307/k8s-project-brokecart`.

1. GitHub **Settings → Environments**: create `learning`.
2. Add Environment secrets `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`; the token needs push rights to the application repositories.
3. Use public application image repositories for this configuration. Private pulls require separate Kubernetes pull-Secret wiring; the CI login is not automatically distributed to nodes.
4. **Settings → Actions → General**: permit the chosen bot image-promotion flow to write repository contents. Protected branch rules still apply.
5. **Settings → Actions → Runners → New self-hosted runner**: select Linux/x64 and use GitHub's current download/checksum instructions.
6. Keep runner files outside the repository, e.g. `Downloads/actions-runner-brokecart/actions-runner`.

Configure the downloaded runner interactively so its short-lived registration token is not saved in an example:

```bash
./config.sh --url https://github.com/SandeepReddy0307/k8s-project-brokecart \
  --name brokecart-local --labels brokecart --work _work
./run.sh
```

Enter the registration token from GitHub when prompted. Runner name identifies the runner in GitHub; `brokecart` is the extra label workflows select; `_work` is its checkout/job workspace. It is not the application runtime volume. Leave this terminal running or deliberately configure a runner service supported by your WSL/systemd environment. Stopping the runner stops CI availability, not the already-running Kubernetes services.

The runner needs Docker, Git, Bash, Java 17, Python/PyYAML and Helm. CI installs Node 22 for frontend; Maven wrapper downloads Maven. A single runner executes one job at a time. Matrix `max-parallel: 2` only permits two builds if two runners exist; do not add a second runner on this laptop while memory is constrained.

No cluster-admin kubeconfig or OpenBao root token is needed by the application build workflows. The persistent runner is trusted infrastructure: workflows are restricted to trusted `main` pushes/manual runs, not arbitrary fork code.

## The three workflows

| File | Trigger/responsibility |
|---|---|
| `.github/workflows/build-images.yaml` | Select changed services, call reusable builds, promote tested image versions |
| `.github/workflows/service-build.yaml` | Reusable Maven/frontend test, Docker build/login/push, credential cleanup |
| `.github/workflows/validate-infrastructure.yaml` | Validate workflow syntax, Helm charts and configuration references; no deployment |

### What rebuilds?

| Change | Result |
|---|---|
| One `services/<name>-service/**` | Only that service's image |
| Several services | Those services |
| `frontend/**` | Frontend only |
| Shared Java library/root Maven wrapper/build inputs | All dependent Java images, including maintenance |
| CI build workflow or CI helper scripts | All 16 images to verify changed build behavior |
| `infra/**` only | Infrastructure validation, no application rebuild |
| Documentation only | No image build |

Manual **Actions → Build changed services → Run workflow** accepts `all`, a single name such as `catalog`, or `catalog,orders,frontend`. Start with `all` on a fresh project before activating Argo. Invalid names are rejected.

### One Catalog source change, completely followed

1. Developer changes Catalog Java source and pushes `main`.
2. `select_services.py` compares commits and emits the Catalog build matrix entry.
3. Reusable build checks out that exact source SHA, verifies Catalog plus shared dependencies, then builds its Dockerfile.
4. It logs in with Environment credentials using `--password-stdin` and a private temporary `DOCKER_CONFIG` under `RUNNER_TEMP`.
5. Image is pushed as `docker.io/<owner>/brokecart-catalog:<full-source-SHA>`.
6. After every selected build succeeds, `check_promotion.py` rejects stale source promotion and `update_images.py` edits only selected image repository/tag fields.
7. Infrastructure validation renders the results. The bot commits/pushes updated values to `main` with write permission limited to that job.
8. Argo detects the values commit, renders Catalog's chart and updates its Deployment.
9. Kubelet pulls the image; startup/Flyway/readiness determine when the Pod serves traffic.
10. Temporary registry credentials are removed in an `always()` cleanup step.

Full-SHA tags identify the build; they are not registry-enforced digest immutability. The workflow does not use mutable `latest`. It does not run `kubectl apply` or application `helm upgrade`.

## Install Argo CD

Prerequisites: working platform, unsealed OpenBao with scoped credentials, validated chart files and published images.

```bash
helm upgrade --install argocd argo/argo-cd \
  --version 10.10.5 --kube-context kind-brokecart \
  --namespace argocd --create-namespace \
  -f infra/platform/argocd-values.yaml --wait --timeout 10m
kubectl --context kind-brokecart apply -f infra/platform/argocd-route.yaml
kubectl --context kind-brokecart -n argocd get pods
```

Open `https://argocd.brokecart.com:8443/`. The root URL was verified; direct `/applications` returned 404 during recovery. Username is `admin`. Read the initial password locally if it has not been changed:

```bash
kubectl --context kind-brokecart -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 --decode
echo
```

`server.insecure: true` means internal HTTP between Kong and Argo server; the public browser connection remains HTTPS at Kong. Dex is disabled. The application controller requests 512Mi, has a 2Gi limit and Go memory limit 1536MiB; status/operation processors are five/two. Its previous 768Mi cap repeatedly OOM-killed it during full-stack synchronization.

Argo components: API/UI server; application-controller compares/syncs state; repo-server fetches Git/renders charts; Redis caches; applicationset-controller handles ApplicationSet resources if authored; notifications-controller is installed but no external notification integration is implied. There is no ApplicationSet manifest in the current application setup.

## Activate the parent Application

```bash
helm dependency build infra/charts/kafka-ui
python3 scripts/ci/validate_infra.py --dependencies
python3 scripts/preflight.py --cluster
kubectl --context kind-brokecart apply -f infra/argocd/root-application.yaml
kubectl --context kind-brokecart -n argocd get applications -w
```

`preflight.py --allow-pending-images` is only for preparation before image publication. Normal activation must reject placeholder owners/`pending-ci`. `--cluster` reads platform readiness; it does not prove the entire business flow.

Parent `brokecart` watches `infra/argocd/applications` on `main`. Each child selects its chart, values and destination namespace with `CreateNamespace=true`. `prune` removes resources deleted from desired config; `selfHeal` corrects drift. Five retries use exponential backoff.

| Parent wave | Children |
|---|---|
| 0 | postgres, redis, kafka, elasticsearch, observability-config |
| 5 | kafka-ui |
| 10 | 14 backends |
| 20 | frontend |
| 30 | maintenance |

Each child also has its **own** internal resource waves: ServiceAccounts -3, SecretStores -2, ExternalSecrets -1, config/Services 0, workloads 1, and later HPA/routes/provisioning as defined by each chart. These wave numbers belong to different sync operations; a child's -3 is not “before every other Application's wave 0” globally.

Argo's custom health Lua waits for ESO Ready conditions, current Certificate readiness, successful child operations/hooks and synced/healthy children. This is why a failed historical sync could block the parent even though Kafka Pods were Ready. Applying all children manually bypasses parent ordering.

## Updating and rolling back

For a normal values change: edit Git → lint/render → commit/push → Argo sync. For code: source push → selective build/promotion → Argo. For a Helm-managed platform value change: edit/review the platform values and run the matching pinned Helm upgrade, then commit the configuration.

```bash
git diff --check
git add infra/values/catalog.yaml
git commit -m "Adjust Catalog configuration"
git push origin main
```

For an Argo-owned application rollback, revert the specific reviewed image/config commit in Git and push it. Do not blindly revert a multi-service promotion or database migration without reviewing the affected services/data compatibility. Auto-sync would otherwise restore a manually rolled-back live image from Git.

`git revert` creates an auditable compensating commit; do not use `git reset --hard`/force push as a deployment rollback recipe. Schema/data rollback is separate from image rollback.

If chart download hits a release-assets timeout, retry the download rather than increasing Kubernetes readiness timeout. You may `helm pull` the exact version to a local `.tgz`, inspect it and use that archive with the same values. Never replace a pinned chart with an arbitrary newer release to get past a network error.
