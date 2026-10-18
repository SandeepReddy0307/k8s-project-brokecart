#!/usr/bin/env python3
"""Render edge/Job charts and verify source-backed public routing boundaries."""
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(chart, release, values, namespace=None, extra=()):
    result = subprocess.run(
        ["helm", "template", release, str(ROOT / "infra/charts" / chart),
         "--namespace", namespace or f"brokecart-{release}", "-f", str(ROOT / values), *extra],
        check=True, text=True, capture_output=True,
    )
    return [item for item in yaml.safe_load_all(result.stdout) if item]


def one(resources, kind):
    return next(item for item in resources if item["kind"] == kind)


frontend = render("frontend", "frontend", "infra/values/frontend.yaml")
deployment = one(frontend, "Deployment")
pod = deployment["spec"]["template"]
container = pod["spec"]["containers"][0]
assert pod["spec"]["securityContext"]["runAsUser"] == 101
assert container["securityContext"]["readOnlyRootFilesystem"]
assert not pod["spec"]["automountServiceAccountToken"]
assert not container.get("envFrom") and not container.get("env")
assert container["readinessProbe"]["httpGet"]["path"] == "/health"
assert one(frontend, "Service")["spec"]["selector"].items() <= pod["metadata"]["labels"].items()
assert not any(item["kind"] in ("ExternalSecret", "ServiceMonitor") for item in frontend)
route = one(frontend, "HTTPRoute")["spec"]
assert route["hostnames"] == ["brokecart.com"]
assert route["parentRefs"][0]["sectionName"] == "https"
assert route["rules"][0]["backendRefs"][0]["name"] == "frontend"
network = one(frontend, "NetworkPolicy")["spec"]
assert network["ingress"][0]["ports"][0]["port"] == 8080
assert network["ingress"][0]["from"][0]["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"] == "kong"
scaled = render("frontend", "frontend", "infra/values/frontend.yaml", extra=("--set", "autoscaling.enabled=true,pdb.enabled=true"))
assert "replicas" not in one(scaled, "Deployment")["spec"]
assert one(scaled, "HorizontalPodAutoscaler")["spec"]["scaleTargetRef"]["name"] == "frontend"
assert one(scaled, "PodDisruptionBudget")["spec"]["selector"]["matchLabels"] == pod["metadata"]["labels"]

maintenance = render("maintenance", "maintenance", "infra/values/maintenance.yaml")
jobs = [item for item in maintenance if item["kind"] == "CronJob"]
assert len(jobs) == 2
tasks = set()
for job in jobs:
    spec = job["spec"]
    assert spec["suspend"] is True and spec["concurrencyPolicy"] == "Forbid"
    job_spec = spec["jobTemplate"]["spec"]
    assert job_spec["activeDeadlineSeconds"] == 120
    template = job_spec["template"]["spec"]
    assert template["serviceAccountName"] == "maintenance"
    assert not template["automountServiceAccountToken"]
    container = template["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"]
    env = {item["name"]: item for item in container["env"]}
    tasks.add(env["TASK"]["value"])
    assert env["INTERNAL_TOKEN"]["valueFrom"]["secretKeyRef"] == {"name": "maintenance-application-security", "key": "internal-token"}
assert tasks == {"expire-reservations", "reconcile-payments"}
secret = one(maintenance, "ExternalSecret")["spec"]
assert secret["data"] == [{"secretKey": "internal-token", "remoteRef": {"key": "brokecart/shared/internal", "property": "token"}}]
assert one(maintenance, "SecretStore")["spec"]["provider"]["vault"]["auth"]["kubernetes"]["role"] == "maintenance-application-secrets"
assert one(maintenance, "NetworkPolicy")["spec"]["ingress"] == []

expected = {
    "catalog": ["/api/catalog"], "pricing": ["/api/pricing"], "identity": ["/api/identity"],
    "cart": ["/api/cart"], "checkout": ["/api/checkout"], "orders": ["/api/orders", "/api/operations/orders"],
    "inventory": ["/api/operations/inventory"], "payments": ["/api/operations/payments"],
    "shipping": ["/api/shipping", "/api/operations/shipping"], "returns": ["/api/returns", "/api/operations/returns"],
    "notifications": ["/api/notifications"], "search": ["/api/search"], "reporting": ["/api/operations/reports"],
}
for service in [*expected, "payment-provider"]:
    resources = render("application", service, f"infra/values/{service}.yaml")
    routes = [item for item in resources if item["kind"] == "HTTPRoute"]
    if service == "payment-provider":
        assert not routes
        continue
    assert len(routes) == 1
    spec = routes[0]["spec"]
    assert spec["parentRefs"][0] == {"name": "brokecart-gateway", "namespace": "kong", "sectionName": "https"}
    assert spec["hostnames"] == ["brokecart.com"]
    rules = spec["rules"]
    paths = [match["path"]["value"] for rule in rules for match in rule["matches"]]
    assert paths == expected[service], (service, paths)
    assert all(path.startswith("/api/") for path in paths)
    assert not any(rule.get("filters") for rule in rules), "Public API paths must not be rewritten"
    assert all(rule["backendRefs"][0]["name"] == service for rule in rules)
    source = "\n".join(path.read_text() for path in (ROOT / "services" / f"{service}-service" / "src/main/java").rglob("*Controller.java"))
    assert all(path in source for path in paths), f"Route missing in actual {service} controllers"

print("PASS: frontend least-privilege workload, suspended maintenance jobs, policies, and 13 public API routes; provider stays internal")
