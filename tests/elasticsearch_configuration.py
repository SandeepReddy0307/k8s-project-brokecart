"""Check rendered security boundaries and script syntax without cluster access."""
import json
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
rendered = subprocess.check_output(["helm", "template", "elasticsearch",
    str(ROOT / "infra/charts/elasticsearch"), "-n", "brokecart-elasticsearch"], text=True)
resources = list(yaml.safe_load_all(rendered))
def get(kind, name):
    return next(r for r in resources if r["kind"] == kind and r["metadata"]["name"] == name)

sts = get("StatefulSet", "elasticsearch")
pod = sts["spec"]["template"]["spec"]
assert sts["spec"]["replicas"] == 1
assert sts["spec"]["persistentVolumeClaimRetentionPolicy"]["whenDeleted"] == "Retain"
assert pod["automountServiceAccountToken"] is False
assert pod["securityContext"]["runAsNonRoot"] is True
volumes = {v["name"]: v for v in pod["volumes"]}
for container in pod["containers"] + pod["initContainers"]:
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert not container["securityContext"]["allowPrivilegeEscalation"]
    assert {m["name"] for m in container["volumeMounts"]} <= set(volumes) | {"data"}
assert pod["containers"][0]["command"] == ["/bin/bash", "/scripts/start.sh"]
scripts = get("ConfigMap", "elasticsearch-scripts")["data"]
# A Pod must check its own listener: the Service excludes unready Pods.
# Keep the certificate's DNS name for hostname verification while using loopback.
assert "--resolve elasticsearch:9200:127.0.0.1" in scripts["check-ready.sh"]
assert "https://elasticsearch:9200/_cluster/health" in scripts["check-ready.sh"]
assert "--cacert /usr/share/elasticsearch/config/tls/ca.crt" in scripts["check-ready.sh"]
assert "--insecure" not in scripts["check-ready.sh"]
for name, script in scripts.items():
    if name.endswith(".sh"):
        subprocess.run(["bash" if name == "start.sh" else "sh", "-n"],
                       input=script, text=True, check=True)
config = yaml.safe_load(get("ConfigMap", "elasticsearch-config")["data"]["elasticsearch.yml"])
assert config["xpack.security.enabled"]
assert config["xpack.security.http.ssl.enabled"]
assert config["xpack.security.transport.ssl.verification_mode"] == "full"
assert config["node.store.allow_mmap"] is False
assert all("/usr/share/elasticsearch/config/tls/" in config[key]
           for key in ("xpack.security.http.ssl.key", "xpack.security.http.ssl.certificate"))
role = json.loads(scripts["search-role.json"])
assert role["cluster"] == []
assert role["indices"] == [{"names": ["brokecart-products"],
                            "privileges": ["read", "write", "create_index"]}]
index = json.loads(scripts["product-index.json"])
assert index["settings"] == {"number_of_shards": 1, "number_of_replicas": 0}
cert = get("Certificate", "elasticsearch")["spec"]
assert "elasticsearch.brokecart-elasticsearch.svc.cluster.local" in cert["dnsNames"]
job = get("Job", "elasticsearch-provisioning")
assert job["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "2"
job_volumes = {v["name"]: v for v in job["spec"]["template"]["spec"]["volumes"]}
assert job_volumes["tls"]["secret"]["items"] == [{"key": "ca.crt", "path": "ca.crt"}]
assert len([r for r in resources if r["kind"] == "ExternalSecret"]) == 2
for script in (ROOT / "infra/bootstrap").glob("*elasticsearch*.sh"):
    subprocess.run(["bash", "-n", str(script)], check=True)
application = yaml.safe_load((ROOT / "infra/argocd/applications/elasticsearch.yaml").read_text())
assert application["spec"]["source"]["path"] == "infra/charts/elasticsearch"
assert application["spec"]["destination"]["namespace"] == "brokecart-elasticsearch"
print(f"PASS: {len(resources)} rendered Elasticsearch resources, TLS, credential boundaries, provisioning and script syntax")
