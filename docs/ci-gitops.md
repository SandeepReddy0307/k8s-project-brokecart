# Building and deploying BrokeCart

Workflow syntax and GitHub expression contexts are checked with pinned, checksum-verified actionlint before infrastructure checks. Run `python3 scripts/ci/check_workflows.py --download` locally before committing workflow changes. Registry configuration is created in a private directory beneath RUNNER_TEMP by a step and shared through GITHUB_ENV; cleanup uses that step's output so it cannot target the runner's normal Docker configuration.

GitHub Actions tests, builds and publishes images. Argo CD applies Kubernetes resources from Git. These are separate responsibilities: workflows never run `helm upgrade`, `kubectl apply` or access the OpenBao root token.

## What has been prepared

- `.github/workflows/build-images.yaml` selects changed services and promotes successful builds.
- `.github/workflows/service-build.yaml` is the reusable implementation for one build target.
- `.github/workflows/validate-infrastructure.yaml` lints and renders charts without deploying anything.
- `scripts/ci/select_services.py` is the change detector.
- `scripts/ci/update_images.py` edits only `image.repository` and `image.tag` in selected values files, preserving surrounding configuration and comments.
- `scripts/ci/check_promotion.py` refuses to promote an old image if newer changes affect that service.
- `infra/argocd/applications/` contains a separate Application for every backend, frontend, maintenance worker, PostgreSQL, Redis, Kafka, Kafka UI and Elasticsearch.

These files do not register a runner, create GitHub secrets, install Argo CD or deploy the applications by themselves.

## One-time GitHub setup

1. In the repository's **Settings → Environments**, create an environment named `learning`.
2. Add environment secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`. Use a Docker Hub access token with push rights for your image repositories. Never put the token in a values file.
3. In **Settings → Actions → General → Workflow permissions**, allow read/write permissions so the image promotion job can commit updated values to this repository. Only that job requests `contents: write`; other jobs request read access.
4. If branch protection blocks direct bot commits, use an approved promotion PR workflow before enabling the pipeline. This version uses a direct bot commit to `main`; it does not bypass branch rules.
5. Register the local WSL Linux x64 self-hosted runner through **Settings → Actions → Runners → New self-hosted runner**. Give it the custom label `brokecart`, in addition to the default `self-hosted`, `linux`, `x64` labels. Register it from a separate runner directory, not inside the application repository.
6. Keep the runner running while builds execute. One runner executes one job at a time. The workflow permits at most two concurrent matrix jobs; two registered runner instances would be needed to use both slots. One runner works sequentially and uses less local memory.

If you choose another environment name, change both build and promotion jobs from `environment: learning` to the same name. Environment secrets are attached to the jobs that need them, including the job inside the reusable workflow.

The runner needs Git, Bash, Java 17, Docker Engine/BuildKit access, Python 3 with PyYAML, Helm 3, and network access to GitHub, Maven Central, npm, Docker Hub and the pinned chart repository. The frontend job installs Node.js 22 with the commit-pinned setup-node action and caches npm downloads, so the host Node.js version does not need upgrading. The checked-in Maven wrapper downloads Maven 3.9.11 as configured in `.mvn/wrapper/maven-wrapper.properties`. The runner does not need cluster administrator kubeconfig for these build jobs.

Use only trusted source on this persistent local runner. These workflows accept pushes to `main` and manual runs on `main`; they deliberately do not run fork pull request code. Registry credentials use a temporary `DOCKER_CONFIG`, stdin login and cleanup, rather than the user's persistent Docker configuration.

## How service selection works

| Change | Images selected |
|---|---|
| `services/catalog-service/**` | catalog only |
| `services/orders-service/**` | orders only |
| Several service directories | those services only |
| `services/maintenance-worker/**` | maintenance only |
| `frontend/**` | frontend only |
| `libraries/**`, root `pom.xml`, Maven wrapper or root `.dockerignore` | all 15 Java modules, including maintenance |
| Build workflow or `scripts/ci/**` | all 16 images, because build behavior changed |
| `infra/**` only | no images; infrastructure validation only |
| Documentation only | no image builds |

All HTTP backends currently depend on `commerce-common`; a shared library change therefore rebuilds all Java modules. Each matrix job runs Maven `verify -pl <selected-module> -am`, which compiles and tests that module plus its Maven dependencies. Frontend runs `npm ci`, unit tests, TypeScript checks and a Vite production build.

Backend Dockerfiles have their own multi-stage Maven build, which packages only the selected module and its Maven dependencies (`-pl services/<module> -am`). Docker BuildKit reuses a locked Maven cache, preventing concurrent image builds from writing to the same dependency cache simultaneously. Only selected images are published. This is separate from the earlier CI test gate, which runs tests. Browser/end-to-end business-flow checks require the deployed stack and are a later deployment verification gate.

## Build → image → Git → deployment

For a catalog source change:

1. A push to `main` identifies catalog as the only build target.
2. Maven verifies catalog and its shared dependency. A failed test stops publication for that job.
3. Docker builds and pushes `docker.io/<DOCKERHUB_USERNAME>/brokecart-catalog:<full-source-Git-SHA>`.
4. Once every selected build succeeds, promotion checks that no newer source changes supersede these builds.
5. Promotion edits only `infra/values/catalog.yaml`, setting its repository and full SHA tag.
6. The GitHub Actions bot commits the image values and pushes them to `main`.
7. Argo CD notices the values change and updates the catalog Deployment.
8. Kubernetes rolls out the image, and readiness determines whether the new Pod receives traffic.

A failed selected build prevents the combined image promotion commit. Images already pushed by other successful jobs remain in Docker Hub but are not promoted. A non-fast-forward promotion push fails safely; run a fresh build after the competing change rather than force-pushing. No mutable `latest` tag is used by these workflows. The source SHA tag identifies the build; image digests can be added later for registry-enforced immutability.

The GitOps bot commit uses `GITHUB_TOKEN`. GitHub does not start new push-triggered workflows from that token's commits, preventing an image-update loop. Argo CD still sees the commit because it watches Git independently. The promotion step validates the edited YAML and renders every chart before committing; the separate infrastructure workflow also checks chart rendering. The bot commit is a record of selected image versions, not a secret.

For the first build, use **Actions → Build changed services → Run workflow → services: `all`**. For an explicit individual rebuild, enter `catalog`; for a subset, enter `catalog,orders,frontend`. Allowed names are the 14 backend names, `maintenance` and `frontend`. Manual input is validated against this allowlist.

Create public Docker Hub repositories if the cluster should pull without registry credentials. Private repositories need a separate image pull Secret and workload wiring; the Docker Hub push token is not automatically copied into Kubernetes.

## Argo CD ownership

Each HTTP backend uses `infra/charts/application` and `../../values/<service>.yaml`, relative to that chart. For example, Application `brokecart-catalog` releases `catalog` into namespace `brokecart-catalog`.

Frontend uses `infra/charts/frontend` with `infra/values/frontend.yaml`. Maintenance uses `infra/charts/maintenance` with `infra/values/maintenance.yaml`. Dependencies use their dedicated charts and own namespaces. Kafka UI retains its upstream chart dependency pinned in `Chart.lock`; validation restores its archive rather than committing the downloaded chart.

The Applications enable automatic sync, pruning, self-healing and namespace creation. Pruning removes resources deleted from desired configuration, so review deletions carefully. Dependency PVC retention is configured within the StatefulSet charts; replication and persistence are not database backups.

Applying Application manifests is the later GitOps activation step after Argo CD is installed and its health customizations from `infra/platform/argocd-values.yaml` are loaded. Adding an Application manifest to Git alone does not create it in the cluster. The root Application at `infra/argocd/root-application.yaml` manages the child Applications. Its sync waves start dependency Applications at wave 0, Kafka UI at 5, backends at 10, frontend at 20 and maintenance at 30. The custom child-Application health check in the Argo CD platform values makes the parent wait for synchronized, healthy children before advancing. Resource waves inside each chart order its own credential, certificate and workload resources. Standalone child Application syncs still have no cross-Application ordering; use the root Application for complete-stack activation.

Argo CD renders Helm templates and owns the resulting Kubernetes objects. It does not create a traditional Helm CLI release, so `helm list` will continue showing the manually installed platform releases, rather than these Argo-owned application releases. Use the Argo UI, `argocd app get`, or Kubernetes resources to inspect application deployment status.

To undo an application version under automatic GitOps, revert the image values commit in Git and push that revert. Argo CD then restores the previous desired image. Do not use `helm rollback` against an Argo-owned application. Schema changes still need a separate backward-compatible database migration plan.

## Checks you can run locally

```bash
python3 tests/ci_configuration.py
python3 scripts/ci/validate_infra.py
```

On a fresh clone, first restore chart dependencies using `python3 scripts/ci/validate_infra.py --dependencies`. That option downloads chart packages; it still does not contact Kubernetes.

Inspect a selection without building:

```bash
python3 scripts/ci/select_services.py --base HEAD~1 --head HEAD
python3 scripts/ci/select_services.py --services catalog,orders,frontend
```

## Official references

- [GitHub Environment secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [GitHub workflow triggering and GITHUB_TOKEN](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow)
- [Argo CD Helm integration](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/)
