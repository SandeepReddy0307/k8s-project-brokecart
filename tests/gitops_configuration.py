"""Verify complete-stack Argo ownership/order and dependency network boundaries."""
from pathlib import Path
import subprocess
import yaml
ROOT = Path(__file__).resolve().parents[1]
apps = [yaml.safe_load(p.read_text()) for p in (ROOT / "infra/argocd/applications").glob("*.yaml")]
assert len(apps) == 22, len(apps)
names = {a["metadata"]["name"] for a in apps}
assert len(names) == len(apps)
for app in apps:
    name = app["metadata"]["name"]
    wave = int(app["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"])
    if name in ("brokecart-postgres", "brokecart-redis", "brokecart-kafka",
                "brokecart-elasticsearch", "brokecart-observability-config"):
        assert wave == 0
    elif name == "brokecart-kafka-ui":
        assert wave == 5
    elif name == "brokecart-frontend":
        assert wave == 20
    elif name == "brokecart-maintenance":
        assert wave == 30
    else:
        assert wave == 10
    spec = app["spec"]
    assert spec["destination"]["server"] == "https://kubernetes.default.svc"
    assert (ROOT / spec["source"]["path"] / "Chart.yaml").is_file()
    for value_file in spec["source"].get("helm", {}).get("valueFiles", []):
        assert (ROOT / spec["source"]["path"] / value_file).is_file()
root = yaml.safe_load((ROOT / "infra/argocd/root-application.yaml").read_text())
assert root["spec"]["source"]["path"] == "infra/argocd/applications"
platform = yaml.safe_load((ROOT / "infra/platform/argocd-values.yaml").read_text())
health = platform["configs"]["cm"]["resource.customizations.health.argoproj.io_Application"]
assert 'phase == "Running"' in health and 'phase == "Failed"' in health
assert 'obj.status.sync.status ~= "Synced"' in health
assert platform["configs"]["params"]["server.insecure"] is True
for service, port in (("postgres",5432),("redis",6379),("kafka",9092),("elasticsearch",9200)):
    rendered = subprocess.check_output(["helm","template",service,str(ROOT / "infra/charts" / service),
                                       "-n","brokecart-"+service],text=True)
    resources = [r for r in yaml.safe_load_all(rendered) if r]
    policy = next(r for r in resources if r["kind"] == "NetworkPolicy")["spec"]
    assert policy["policyTypes"] == ["Ingress"]
    assert policy["podSelector"]["matchLabels"]["app.kubernetes.io/name"] == service
    assert port in {p["port"] for rule in policy["ingress"] for p in rule["ports"]}
    for rule in policy["ingress"]:
        for peer in rule["from"]:
            assert "namespaceSelector" in peer or "podSelector" in peer
    if service == "redis":
        assert policy["ingress"][0]["from"][0]["namespaceSelector"]["matchExpressions"][0]["values"] == [
            "brokecart-cart","brokecart-redis"]
    if service == "kafka":
        assert {9092,9093,9094} == {p["port"] for rule in policy["ingress"] for p in rule["ports"]}
print("PASS: 22 child Applications, deployment waves, provisioning-aware health and dependency network policies")
