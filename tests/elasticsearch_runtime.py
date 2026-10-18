#!/usr/bin/env python3
"""Disposable Docker verification of the rendered chart; never accesses kind/OpenBao."""
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:8.17.6"

def run(*args, **kw):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kw).stdout

def main():
    docs = list(yaml.safe_load_all(run("helm", "template", "elasticsearch",
        str(ROOT / "infra/charts/elasticsearch"), "-n", "brokecart-elasticsearch")))
    cm = {d["metadata"]["name"]: d["data"] for d in docs if d["kind"] == "ConfigMap"}
    name = "brokecart-es-check-" + secrets.token_hex(5)
    with tempfile.TemporaryDirectory(prefix="brokecart-es-check-") as temporary:
        base = Path(temporary)
        # The production process uses UID 1000 and projected files with fsGroup.
        base.chmod(0o755)
        for folder in ("settings", "scripts", "tls", "admin", "search", "config", "data", "logs"):
            (base / folder).mkdir(mode=0o755)
        for folder in ("config", "data", "logs"):
            os.chmod(base / folder, 0o777)
        (base / "settings/elasticsearch.yml").write_text(cm["elasticsearch-config"]["elasticsearch.yml"])
        for filename, content in cm["elasticsearch-scripts"].items():
            (base / "scripts" / filename).write_text(content)
        admin, password = secrets.token_hex(24), secrets.token_hex(24)
        (base / "admin/password").write_text(admin)
        (base / "search/password").write_text(password)
        (base / "search/username").write_text("brokecart_search")
        run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(base / "tls/tls.key"), "-out", str(base / "tls/tls.crt"),
            "-days", "1", "-subj", "/CN=elasticsearch",
            "-addext", "subjectAltName=DNS:elasticsearch,IP:127.0.0.1")
        shutil.copyfile(base / "tls/tls.crt", base / "tls/ca.crt")
        os.chmod(base / "tls/tls.key", 0o644)
        mounts = []
        for folder, target, ro in (
            ("config", "/usr/share/elasticsearch/config", False),
            ("data", "/usr/share/elasticsearch/data", False),
            ("logs", "/usr/share/elasticsearch/logs", False),
            ("settings", "/settings", True), ("scripts", "/scripts", True),
            ("tls", "/usr/share/elasticsearch/config/tls", True), ("admin", "/auth/admin", True),
            ("search", "/auth/search", True)):
            mounts.extend(["-v", f"{base / folder}:{target}" + (":ro" if ro else "")])
        try:
            # Same init script, with the original image config directory available.
            run("docker", "run", "--rm", "--user", "1000:0",
                "-v", f"{base / 'config'}:/work-config",
                "-v", f"{base / 'settings'}:/settings:ro",
                "-v", f"{base / 'scripts'}:/scripts:ro",
                "--entrypoint", "/bin/sh", IMAGE, "/scripts/prepare-config.sh")
            run("docker", "run", "-d", "--name", name, "--label", "brokecart.elasticsearch-check=true",
                "--user", "1000:0", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--memory", "1536m",
                "--tmpfs", "/tmp:uid=1000,gid=0,mode=1777",
                "--add-host", "elasticsearch:127.0.0.1", "-p", "127.0.0.1::9200",
                *mounts, "--entrypoint", "/bin/bash",
                "-e", "ES_JAVA_OPTS=-Xms512m -Xmx512m -XX:ActiveProcessorCount=2", IMAGE, "/scripts/start.sh")
            for _ in range(30):
                inspected = json.loads(run("docker", "inspect", name))[0]
                bindings = inspected["NetworkSettings"]["Ports"].get("9200/tcp")
                if bindings:
                    binding = bindings[0]
                    break
                if inspected["State"]["Status"] == "exited":
                    raise RuntimeError("Elasticsearch container exited before binding its port")
                time.sleep(1)
            else:
                raise RuntimeError("Docker did not publish Elasticsearch's port")
            endpoint = f"https://127.0.0.1:{binding['HostPort']}"
            context = ssl.create_default_context(cafile=str(base / "tls/ca.crt"))
            def request(path, user="elastic", pwd=admin, method="GET", body=None, ctx=context):
                headers = {"Authorization": "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode(),
                           "Content-Type": "application/json"}
                req = urllib.request.Request(endpoint + path,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers=headers, method=method)
                try:
                    with urllib.request.urlopen(req, context=ctx, timeout=10) as result:
                        return result.status, json.load(result)
                except urllib.error.HTTPError as error:
                    return error.code, {}
            for _ in range(90):
                try:
                    if request("/_cluster/health")[0] == 200:
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(2)
            else:
                raise RuntimeError("Elasticsearch startup timed out")
            run("docker", "exec", name, "/bin/sh", "/scripts/check-ready.sh")
            print("PASS: non-root Elasticsearch starts with a read-only root filesystem and verified HTTPS", flush=True)
            for _ in range(2):
                run("docker", "exec", "-e", "ELASTICSEARCH_CA=/usr/share/elasticsearch/config/tls/ca.crt", name, "/bin/sh", "/scripts/provision.sh")
            print("PASS: provisioning is repeatable", flush=True)
            assert request("/brokecart-products/_doc/test?refresh=true", "brokecart_search", password,
                "PUT", {"name": "BrokeCart mug", "description": "Coffee", "category": "home"})[0] == 201
            status, result = request("/brokecart-products/_search", "brokecart_search", password,
                "POST", {"query": {"match": {"name": "mug"}}})
            assert status == 200 and result["hits"]["total"]["value"] == 1
            assert request("/private-orders/_doc/test", "brokecart_search", password, "PUT", {"id": 1})[0] == 403
            assert request("/_security/user", "brokecart_search", password)[0] == 403
            assert request("/brokecart-products", "brokecart_search", "wrong")[0] == 401
            print("PASS: search identity indexes/searches products; other indices, security administration and wrong passwords are rejected", flush=True)
            try:
                request("/", ctx=ssl.create_default_context())
            except (ssl.SSLError, urllib.error.URLError):
                pass
            else:
                raise AssertionError("Untrusted certificate was accepted")
            run("docker", "restart", name)
            # Docker may allocate a different ephemeral host port on restart.
            binding = json.loads(run("docker", "inspect", name))[0]["NetworkSettings"]["Ports"]["9200/tcp"][0]
            endpoint = f"https://127.0.0.1:{binding['HostPort']}"
            for _ in range(90):
                try:
                    status, result = request("/brokecart-products/_doc/test", "brokecart_search", password)
                    if status == 200 and result.get("found"):
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(2)
            else:
                raise RuntimeError("Persisted document/credentials missing after restart")
            print("PASS: document and native-user credentials survive container restart; untrusted TLS is rejected", flush=True)
        except Exception:
            # Keep diagnostic output private on failure; it contains no test password by design.
            logs = subprocess.run(["docker", "logs", "--tail", "80", name],
                                  text=True, capture_output=True)
            Path("/tmp/brokecart-elasticsearch-test.log").write_text(logs.stdout + logs.stderr)
            raise
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)

if __name__ == "__main__":
    main()
