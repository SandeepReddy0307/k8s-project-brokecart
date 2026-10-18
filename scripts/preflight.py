#!/usr/bin/env python3
"""Read-only readiness checks before applying the root Argo CD Application."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--cluster", action="store_true", help="also inspect existing kind platform readiness")
parser.add_argument("--allow-pending-images", action="store_true", help="configuration review only; not permission to deploy")
args = parser.parse_args()
failures = []
values = sorted((ROOT / "infra/values").glob("*.yaml"))
for path in values:
    image = yaml.safe_load(path.read_text())["image"]
    pending = ("replace-with-" in image["repository"] or image["tag"] == "pending-ci")
    if pending and not args.allow_pending_images:
        failures.append(f"{path.relative_to(ROOT)} still needs its CI-published image")
    elif not pending and not re.fullmatch(r"[0-9a-f]{40}", str(image["tag"])):
        failures.append(f"{path.relative_to(ROOT)} image.tag must be a full Git commit SHA")
if len(values) != 16:
    failures.append(f"Expected 16 application image values files, found {len(values)}")
platform = yaml.safe_load((ROOT / "infra/platform/argocd-values.yaml").read_text())
for kind in ("argoproj.io_Application", "external-secrets.io_SecretStore",
             "external-secrets.io_ExternalSecret", "cert-manager.io_Certificate"):
    if f"resource.customizations.health.{kind}" not in platform["configs"]["cm"]:
        failures.append(f"Missing Argo CD health customization: {kind}")

def get(kind, name=None, namespace=None):
    command = ["kubectl", "--context", "kind-brokecart"]
    if namespace:
        command += ["-n", namespace]
    command += ["get", kind]
    if name:
        command.append(name)
    command += ["-o", "json"]
    return json.loads(subprocess.check_output(command, text=True, stderr=subprocess.PIPE))

if args.cluster:
    try:
        nodes = get("nodes")["items"]
        if len(nodes) != 3 or any(not any(c["type"] == "Ready" and c["status"] == "True"
            for c in n["status"]["conditions"]) for n in nodes):
            failures.append("Expected three Ready kind nodes")
        for crd in ("applications.argoproj.io", "servicemonitors.monitoring.coreos.com",
                    "prometheusrules.monitoring.coreos.com", "externalsecrets.external-secrets.io",
                    "secretstores.external-secrets.io", "certificates.cert-manager.io",
                    "httproutes.gateway.networking.k8s.io"):
            get("crd", crd)
        storage = get("storageclass", "standard")
        if storage.get("volumeBindingMode") != "WaitForFirstConsumer":
            failures.append("Unexpected standard StorageClass binding mode")
        issuer = get("clusterissuer", "brokecart-local-ca")
        gateway = get("gateway", "brokecart-gateway", "kong")
        metrics = get("apiservice", "v1beta1.metrics.k8s.io")
        for obj, condition in ((issuer, "Ready"), (gateway, "Programmed"), (metrics, "Available")):
            if not any(c["type"] == condition and c["status"] == "True"
                       for c in obj.get("status", {}).get("conditions", [])):
                failures.append(f"{obj['kind']}/{obj['metadata']['name']} is not {condition}")
        bao = get("pod", "openbao-0", "openbao")
        if not any(c["type"] == "Ready" and c["status"] == "True"
                   for c in bao.get("status", {}).get("conditions", [])):
            failures.append("OpenBao is not Ready (check initialization/unseal)")
    except (subprocess.CalledProcessError, KeyError, ValueError) as error:
        failures.append("Platform inspection failed: " + str(error))
if failures:
    for failure in failures:
        print("BLOCKED: " + failure)
    sys.exit(1)
print("PASS: configuration preflight" + (" and existing platform readiness" if args.cluster else ""))
if args.allow_pending_images:
    print("Pending image references were allowed for review; this is not deployment readiness.")
else:
    print("Image tags are populated. Registry availability, OpenBao roles and live behavior still require verification.")
