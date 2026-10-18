"""Validate catalog's rendered resource references and workload security."""
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
def render(*flags):
    return subprocess.check_output(["helm", "template", "catalog", "infra/charts/application",
        "-n", "brokecart-catalog", "-f", "infra/values/catalog.yaml", *flags], cwd=ROOT, text=True)
resources = [r for r in yaml.safe_load_all(render()) if r]
def get(kind, name):
    return next(r for r in resources if r["kind"] == kind and r["metadata"]["name"] == name)

deployment = get("Deployment", "catalog")
pod = deployment["spec"]["template"]["spec"]
container = pod["containers"][0]
env = {e["name"]: e for e in container["env"]}
order = [e["name"] for e in container["env"]]
assert order.index("DB_NAME") < order.index("DB_URL")
assert "$(DB_NAME)?sslmode=verify-full&sslrootcert=/etc/postgres-ca/ca.crt" in env["DB_URL"]["value"]
assert "JWT_PRIVATE_KEY" not in env
assert pod["automountServiceAccountToken"] is False
assert get("ServiceAccount", pod["serviceAccountName"])["automountServiceAccountToken"] is False
assert pod["securityContext"]["runAsUser"] == 10001
assert container["securityContext"]["readOnlyRootFilesystem"] is True
assert container["securityContext"]["allowPrivilegeEscalation"] is False
assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
secrets = {r["spec"]["target"]["name"]: (
               set(r["spec"]["target"]["template"]["data"])
               if "template" in r["spec"]["target"] else {d["secretKey"] for d in r["spec"]["data"]})
           for r in resources if r["kind"] == "ExternalSecret"}
for e in container["env"]:
    if "valueFrom" in e:
        ref = e["valueFrom"]["secretKeyRef"]
        assert ref["key"] in secrets[ref["name"]], e["name"]
configmaps = {r["metadata"]["name"]: r for r in resources if r["kind"] == "ConfigMap"}
for ref in container["envFrom"]:
    assert ref["configMapRef"]["name"] in configmaps
volumes = {v["name"]: v for v in pod["volumes"]}
for mount in container["volumeMounts"]:
    volume = volumes[mount["name"]]
    if "configMap" in volume:
        assert volume["configMap"]["name"] in configmaps
kafka_mount = next(m for m in container["volumeMounts"] if m["name"] == "kafka-config")
assert kafka_mount["mountPath"] == "/etc/kafka-client"
assert env["SPRING_CONFIG_ADDITIONAL_LOCATION"]["value"] == "file:/etc/kafka-client/kafka.yaml"
service = get("Service", "catalog")
assert int(get("HorizontalPodAutoscaler", "catalog")["metadata"]["annotations"][
    "argocd.argoproj.io/sync-wave"]) > int(deployment["metadata"]["annotations"][
    "argocd.argoproj.io/sync-wave"])
assert service["spec"]["selector"] == deployment["spec"]["selector"]["matchLabels"]
assert all(deployment["spec"]["template"]["metadata"]["labels"][k] == v
           for k, v in service["spec"]["selector"].items())
assert service["spec"]["ports"][0]["targetPort"] == "http"
assert next(p for p in container["ports"] if p["name"] == "http")["containerPort"] == 8080
monitor = get("ServiceMonitor", "catalog")
assert monitor["metadata"]["labels"]["release"] == "monitoring"
assert monitor["spec"]["namespaceSelector"]["matchNames"] == ["brokecart-catalog"]
assert all(service["metadata"]["labels"][k] == v
           for k, v in monitor["spec"]["selector"]["matchLabels"].items())
endpoint = monitor["spec"]["endpoints"][0]
assert endpoint["port"] in {p["name"] for p in service["spec"]["ports"]}
assert endpoint["path"] == "/actuator/prometheus"
assert endpoint["scrapeTimeout"] == "10s" and endpoint["interval"] == "30s"
assert not any(r["kind"] == "ServiceMonitor" for r in yaml.safe_load_all(
    render("--set", "monitoring.enabled=false")) if r)
for kind, path in [("startupProbe", "/actuator/health/liveness"),
                   ("readinessProbe", "/actuator/health/readiness"),
                   ("livenessProbe", "/actuator/health/liveness")]:
    assert container[kind]["httpGet"] == {"path": path, "port": "http"}
for r in resources:
    if r["kind"] in ("ExternalSecret", "SecretStore", "ServiceAccount"):
        assert int(r["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]) < 0
disabled = [r for r in yaml.safe_load_all(render("--set", "kafka.enabled=false")) if r]
d = next(r for r in disabled if r["kind"] == "Deployment")
assert "KAFKA_SASL_JAAS_CONFIG" not in {e["name"] for e in d["spec"]["template"]["spec"]["containers"][0]["env"]}
disabled_env = {e["name"]: e for e in d["spec"]["template"]["spec"]["containers"][0]["env"]}
assert disabled_env["KAFKA_ENABLED"]["value"] == "false"
assert "SPRING_CONFIG_ADDITIONAL_LOCATION" not in disabled_env
assert not any(v["name"] == "kafka-config" for v in d["spec"]["template"]["spec"]["volumes"])
for flags, expected in [
    (["--set", "security.enabled=false"], "requires security.enabled"),
    (["--set", "image.repository="], "image.repository is required")]:
    result = subprocess.run(["helm", "template", "catalog", "infra/charts/application",
        "-f", "infra/values/catalog.yaml", *flags], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode != 0 and expected in result.stderr
print(f"PASS: {len(resources)} catalog resources; Secret/ConfigMap references, DB TLS, Kafka mounts, probes, selectors and Pod security")
