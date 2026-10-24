# BrokeCart: complete build, deployment and operations handbook

**Full cart, empty wallet.** This handbook explains the actual BrokeCart repository and the local deployment completed on 2026-10-24. Read it in the order below. Commands are examples to run deliberately, not a script to paste over the running installation.

## Reading order

| Chapter | What you will learn |
|---|---|
| [1. Architecture and Kubernetes basics](01-architecture.md) | Components, resource types, namespaces, request flow, ownership, limitations |
| [2. Cluster, networking, Kong and certificates](02-platform.md) | kind, Cilium, Metrics Server, Gateway API, Kong, local DNS, CA trust |
| [3. OpenBao and External Secrets](03-secrets.md) | Initialize/unseal, Kubernetes authentication, policies, roles, service accounts, bootstrap scripts |
| [4. Observability](04-observability.md) | Prometheus, Grafana, Loki, Fluent Bit, Tempo, OpenTelemetry, queries and alerts |
| [5. Datastores and Kafka](05-data-services.md) | PostgreSQL provisioning, Redis, three-node KRaft, topics/partitions/ACLs, Elasticsearch, Kafka UI |
| [6. Every application service](06-services.md) | All 14 backends, frontend, maintenance worker, dependencies, Kubernetes resources and verification |
| [7. Helm, Docker, GitHub Actions and Argo CD](07-delivery.md) | Values/templates, builds, selective CI, runner, deployment waves, rollback |
| [8. Operations, troubleshooting and testing](08-operations.md) | Start after shutdown, daily checks, incident recipes, laptop sizing, future business-flow tests |
| [9. File-by-file reference](09-file-reference.md) | Every infrastructure, platform, bootstrap and CI file, plus source/build entry points |

Follow chapters 2–5 to prepare a **new** cluster, then chapter 7 to publish images and activate Argo CD. Chapter 6 explains what those releases deploy; chapter 8 is the daily operational guide. For an already running cluster, begin with chapter 8 rather than reinstalling everything.

## Commands and local assumptions

- Repository: `/mnt/c/Users/sandeep.reddy01/Downloads/k8s-project-2` in WSL; Windows path `C:\Users\sandeep.reddy01\Downloads\k8s-project-2`.
- Kubernetes context: `kind-brokecart`. Commands specify it so they do not depend on the currently selected namespace/context.
- Shell: Bash in WSL unless a block explicitly says PowerShell or Windows hosts file.
- Git remote: `https://github.com/SandeepReddy0307/k8s-project-brokecart.git`, branch `main`.
- Browser domain: `brokecart.com`, mapped locally. This is local name resolution, not public DNS ownership or a public deployment.
- HTTPS: `8443`; HTTP: `8080`. `:8443` is part of the browser origin.
- Files contain the configuration; Git is the desired-state record. Never put actual passwords, private keys, unseal keys or bootstrap tokens into examples or commits.

Start an example session with:

```bash
cd /mnt/c/Users/sandeep.reddy01/Downloads/k8s-project-2
kubectl config current-context
kubectl --context kind-brokecart get nodes
```

Copy only commands inside a code block. Explanatory sentences are not shell commands. A continuation backslash must be the last character on its line; do not type `\ \`.

## What was verified, and what is still pending

The final recovery checks on 2026-10-24 confirmed:

- All 23 Argo CD Applications—one parent and 22 children—were Synced/Healthy.
- No workload Pod was unready in the final snapshot.
- Each of the 14 backend Deployments had one desired and one Ready replica.
- All 14 backend HPAs had `minReplicas: 1` and `maxReplicas: 1`.
- All 14 backend runtime containers had a 384Mi memory limit and zero rollout surge.
- PostgreSQL had 34 connections at the check, rather than exhausting its 100-connection limit.
- Kong gateway/controller were Ready. Storefront `/` and Argo CD `/` returned HTTP 200 through verified HTTPS.
- WSL had about 2.9Gi memory available. This is a point-in-time measurement, not a memory guarantee under load.

The direct Argo CD `/applications` URL returned 404 during verification; use `https://argocd.brokecart.com:8443/`. Do not interpret the working root URL as proof that every deep link works.

**The complete deployed customer/operator shopping journey has not yet been tested by the user.** Healthy Pods and successful page requests are infrastructure checks, not proof of payment, stock, cancellation, shipping and return correctness. Chapter 8 gives the pending acceptance checklist. Earlier disposable application tests are recorded in [verification](../verification.md); those are distinct from this deployed-cluster acceptance test.

## Ownership rule

Platform installations are traditional Helm releases. Application/datastore Kubernetes resources are managed by Argo CD from Helm templates. Do not run an independent `helm upgrade --install catalog ...` over the Argo-owned Catalog resources.

An emergency live change must match a reviewed Git change or be reconciled back into Git afterward. During recovery we temporarily applied the already-committed one-replica HPA settings directly so the overloaded controller could catch up; that was an incident action, not a second deployment pipeline.

## Official references

The repository files are the primary reference for this project. These upstream explanations help when exploring beyond it:

- [kind configuration](https://kind.sigs.k8s.io/docs/user/configuration/)
- [Cilium on kind](https://docs.cilium.io/en/stable/installation/kind/)
- [Kubernetes concepts](https://kubernetes.io/docs/concepts/)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [Helm documentation](https://helm.sh/docs/)
- [OpenBao Kubernetes authentication](https://openbao.org/docs/auth/kubernetes/)
- [External Secrets Vault-compatible provider](https://external-secrets.io/latest/provider/hashicorp-vault/)
- [Argo CD sync phases and waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)

Versions in the next chapters reproduce the observed installation. They are not a claim that these are the latest releases or that upgrading can be done without compatibility checks.
