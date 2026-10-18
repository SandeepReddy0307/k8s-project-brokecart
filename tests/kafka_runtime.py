"""Isolated Docker verification of the Kafka chart; never touches kind or OpenBao.

Requires Docker, Helm, OpenSSL, and PyYAML. Uses disposable synthetic credentials,
three Kafka containers, and one Kafbat container. Removes only its own fixtures.
"""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import yaml
from kafka_configuration import ROOT, render, resource


def run(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, check=True, **kwargs).stdout.strip()


def main():
    values = yaml.safe_load((ROOT / "infra/charts/kafka/values.yaml").read_text())
    kafka = render("kafka", "brokecart-kafka")
    ui = render("kafka-ui", "brokecart-kafka-ui")
    image = values["image"]["repository"] + ":" + values["image"]["tag"]
    ui_values = yaml.safe_load((ROOT / "infra/charts/kafka-ui/values.yaml").read_text())["kafka-ui"]
    ui_image = "/".join([ui_values["image"]["registry"], ui_values["image"]["repository"]]) + ":" + ui_values["image"]["tag"]
    prefix = "brokecart-kafka-check-" + uuid.uuid4().hex[:8]
    label = "brokecart.kafka-check=" + prefix
    containers = []
    network_created = False
    workspace = Path(tempfile.mkdtemp(prefix=prefix + "-"))
    workspace.chmod(0o755)
    hosts = [f"kafka-{i}.kafka-headless.brokecart-kafka.svc.cluster.local" for i in range(3)]
    bootstrap = hosts[0] + ":9092"
    passwords = {"admin": secrets.token_hex(24), "store": secrets.token_hex(24), "browser": secrets.token_hex(24)}
    try:
        print("Preparing isolated Kafka TLS fixtures", flush=True)
        tls = workspace / "tls"; auth = workspace / "auth"; clients = workspace / "clients"
        for directory in [tls, auth, clients]: directory.mkdir()
        (auth / "admin-username").write_text("kafka_admin")
        (auth / "admin-password").write_text(passwords["admin"])
        (auth / "keystore-password").write_text(passwords["store"])
        for service in values["auth"]["clients"]:
            directory = clients / service; directory.mkdir()
            passwords[service] = secrets.token_hex(24)
            (directory / "username").write_text("brokecart_" + service.replace("-", "_"))
            (directory / "password").write_text(passwords[service])
        run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
             "-subj", "/CN=BrokeCart disposable test CA", "-addext", "basicConstraints=critical,CA:TRUE",
             "-keyout", str(tls / "ca.key"), "-out", str(tls / "ca.crt")])
        run(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=brokecart-kafka",
             "-keyout", str(tls / "server.key"), "-out", str(tls / "server.csr")])
        (tls / "extensions").write_text("subjectAltName=" + ",".join("DNS:" + h for h in hosts)
                                       + ",DNS:kafka.brokecart-kafka.svc.cluster.local\n"
                                       + "extendedKeyUsage=serverAuth,clientAuth\n")
        run(["openssl", "x509", "-req", "-in", str(tls / "server.csr"), "-CA", str(tls / "ca.crt"),
             "-CAkey", str(tls / "ca.key"), "-CAcreateserial", "-days", "2", "-extfile", str(tls / "extensions"),
             "-out", str(tls / "server.crt")])
        run(["openssl", "pkcs12", "-export", "-inkey", str(tls / "server.key"), "-in", str(tls / "server.crt"),
             "-certfile", str(tls / "ca.crt"), "-name", "kafka", "-passout", "env:TEST_STORE_PASSWORD",
             "-out", str(tls / "keystore.p12")], env={**os.environ, "TEST_STORE_PASSWORD": passwords["store"]})
        run(["docker", "run", "--rm", "--label", label, "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
             "-v", f"{tls}:/certificates", "-e", "TEST_STORE_PASSWORD=" + passwords["store"],
             "--entrypoint", "keytool", image, "-importcert", "-noprompt", "-alias", "ca",
             "-file", "/certificates/ca.crt", "-keystore", "/certificates/truststore.p12",
             "-storetype", "PKCS12", "-storepass:env", "TEST_STORE_PASSWORD"], timeout=120)
        for name in ["keystore.p12", "truststore.p12"]: (tls / name).chmod(0o644)
        (workspace / "server.properties").write_text(resource(kafka, "ConfigMap", "kafka-config")["data"]["server.properties"])
        shutil.copy(ROOT / "infra/charts/kafka/files/start-kafka.sh", workspace)
        topic_scripts = resource(kafka, "ConfigMap", "kafka-topic-provisioning")["data"]
        for name, content in topic_scripts.items(): (workspace / name).write_text(content)
        for service, username, password in [("admin", "kafka_admin", passwords["admin"])] + [
                (s, "brokecart_" + s.replace("-", "_"), passwords[s]) for s in values["auth"]["clients"]]:
            (workspace / (service + ".properties")).write_text(
                "security.protocol=SASL_SSL\nsasl.mechanism=PLAIN\n"
                "ssl.truststore.type=PKCS12\nssl.truststore.location=/etc/kafka-tls/truststore.p12\n"
                f"ssl.truststore.password={passwords['store']}\n"
                "ssl.endpoint.identification.algorithm=https\n"
                f'sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="{username}" password="{password}";\n')
        wrong = (workspace / "admin.properties").read_text().replace(passwords["admin"], secrets.token_hex(24))
        (workspace / "wrong.properties").write_text(wrong)
        run(["docker", "network", "create", "--label", label, prefix]); network_created = True
        for i, host in enumerate(hosts):
            name = f"{prefix}-{i}"; containers.append(name)
            data = workspace / f"data-{i}"; data.mkdir()
            aliases = ["--network-alias", host]
            if i == 0:
                aliases += ["--network-alias", "kafka.brokecart-kafka.svc.cluster.local"]
            run(["docker", "run", "-d", "--name", name, "--label", label,
                 "--network", prefix, *aliases,
                 "--read-only", "--tmpfs", "/tmp:rw,size=256m,mode=1777", "--memory", "1g", "--cpus", "2",
                 "--user", "1000:1000", "-v", f"{workspace}:/verification:ro",
                 "-v", f"{data}:/var/lib/kafka/data", "-v", f"{workspace}:/etc/kafka-config:ro",
                 "-v", f"{auth}:/etc/kafka-auth:ro", "-v", f"{tls}:/etc/kafka-tls:ro",
                 "-v", f"{clients}:/etc/kafka-clients:ro",
                 "-e", f"POD_NAME=kafka-{i}", "-e", "POD_NAMESPACE=brokecart-kafka",
                 "-e", "CLUSTER_ID=" + values["kraft"]["clusterId"],
                 "-e", "KAFKA_HEAP_OPTS=" + values["jvm"]["heapOpts"],
                 "-e", "JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2", "-e", "LOG_DIR=/tmp/kafka-logs",
                 "--entrypoint", "/bin/bash", image, "/verification/start-kafka.sh"])

        def execute(args, *, checked=True, input=None, timeout=90, container=None, extra_env=None):
            cmd = ["docker", "exec", "-i", "-e", "KAFKA_HEAP_OPTS=-Xms64m -Xmx128m",
                   "-e", "JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2", "-e", "LOG_DIR=/tmp/tools-logs"]
            for key, value in (extra_env or {}).items(): cmd += ["-e", key + "=" + value]
            cmd += [container or containers[0], *args]
            return subprocess.run(cmd, input=input, text=True, capture_output=True, check=checked, timeout=timeout)

        def tool(name, args, *, client="admin", bootstrap_server=bootstrap, **kwargs):
            return execute(["timeout", "35s", f"/opt/kafka/bin/kafka-{name}.sh", "--bootstrap-server", bootstrap_server,
                            "--command-config", f"/verification/{client}.properties", *args], **kwargs)

        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            result = tool("topics", ["--list"], checked=False)
            if result.returncode == 0: break
            time.sleep(3)
        else: raise RuntimeError("Kafka TLS/admin connection failed to become ready")
        print("PASS: three-node KRaft cluster starts using TLS and administrator authentication", flush=True)
        env = {"BOOTSTRAP_SERVERS": bootstrap, "CLIENT_CONFIG": "/verification/admin.properties"}
        execute(["/bin/bash", "/verification/create-topics.sh"], extra_env=env, timeout=240)
        execute(["/bin/bash", "/verification/apply-acls.sh"], extra_env=env, timeout=600)
        listing = tool("topics", ["--list"]).stdout.splitlines()
        expected = set(values["topics"]["names"]) | {t + ".DLT" for t in values["topics"]["names"]}
        assert expected <= set(listing)
        description = tool("topics", ["--describe", "--topic", "inventory.commands"]).stdout
        assert "PartitionCount: 3" in description and "ReplicationFactor: 3" in description
        print("PASS: 18 replicated topics and application/UI ACL provisioning", flush=True)

        def produce(topic, client, message, checked=True):
            return execute(["timeout", "35s", "/opt/kafka/bin/kafka-console-producer.sh", "--bootstrap-server", bootstrap,
                            "--producer.config", f"/verification/{client}.properties", "--topic", topic, "--sync",
                            "--producer-property", "acks=all", "--producer-property", "enable.idempotence=true",
                            "--producer-property", "max.block.ms=10000", "--producer-property", "request.timeout.ms=5000",
                            "--producer-property", "delivery.timeout.ms=20000"], input=message + "\n", checked=checked)

        produce("inventory.commands", "orders", "brokecart-fixture-1")
        consumed = execute(["timeout", "35s", "/opt/kafka/bin/kafka-console-consumer.sh", "--bootstrap-server", bootstrap,
                            "--consumer.config", "/verification/inventory.properties", "--topic", "inventory.commands",
                            "--group", "inventory-service", "--from-beginning", "--max-messages", "1", "--timeout-ms", "25000"])
        assert "brokecart-fixture-1" in consumed.stdout
        print("PASS: orders produces and inventory consumes using separate scoped credentials", flush=True)
        denied = produce("catalog.events", "orders", "must-not-be-written", checked=False)
        assert "Authorization" in denied.stdout + denied.stderr, "Unauthorized producer was not rejected"
        bad = tool("topics", ["--list"], client="wrong", checked=False)
        assert bad.returncode != 0 and "Authentication" in bad.stdout + bad.stderr
        bad_host = tool("topics", ["--list"], bootstrap_server="127.0.0.1:9092", checked=False)
        assert bad_host.returncode != 0 and any(s in bad_host.stdout + bad_host.stderr for s in ("SSLHandshake", "subject alternative", "CertificateException"))
        print("PASS: unauthorized topic writes, incorrect passwords, and TLS hostname mismatches are rejected", flush=True)
        ui_listing = tool("topics", ["--list"], client="kafka-ui").stdout.splitlines()
        assert expected <= set(ui_listing)
        ui_denied = produce("inventory.commands", "kafka-ui", "must-not-be-written", checked=False)
        assert "Authorization" in ui_denied.stdout + ui_denied.stderr
        print("PASS: UI Kafka identity can inspect topics and cannot produce", flush=True)

        print("Preparing Kafka UI browser fixture (downloads image if absent)", flush=True)
        ui_name = prefix + "-ui"; containers.append(ui_name)
        (workspace / "ui-config.yaml").write_text(resource(ui, "ConfigMap", "kafka-ui-fromvalues")["data"]["config.yml"])
        jaas = ('org.apache.kafka.common.security.plain.PlainLoginModule required '
                f'username="brokecart_kafka_ui" password="{passwords["kafka-ui"]}";')
        run(["docker", "run", "-d", "--name", ui_name, "--label", label, "--network", prefix,
             "--read-only", "--tmpfs", "/tmp:rw,size=256m,mode=1777", "--memory", "768m", "--cpus", "2",
             "--user", "1000:2000", "-p", "127.0.0.1::8080", "-v", f"{workspace}:/verification:ro",
             "-v", f"{tls}:/etc/kafka-ca:ro", "-e", "SPRING_CONFIG_ADDITIONAL_LOCATION=/verification/ui-config.yaml",
             "-e", "JAVA_TOOL_OPTIONS=-XX:MaxRAMPercentage=65.0 -XX:ActiveProcessorCount=2",
             "-e", "AUTH_TYPE=LOGIN_FORM", "-e", "DYNAMIC_CONFIG_ENABLED=false",
             "-e", "SPRING_SECURITY_USER_NAME=kafka_viewer", "-e", "SPRING_SECURITY_USER_PASSWORD=" + passwords["browser"],
             "-e", "KAFKA_SASL_JAAS_CONFIG=" + jaas, ui_image], timeout=300)
        address = run(["docker", "port", ui_name, "8080/tcp"]).splitlines()[0]
        url = "http://" + address
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                             urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            try:
                with opener.open(url + "/actuator/health", timeout=3) as response:
                    if response.status == 200: break
            except (urllib.error.URLError, OSError): pass
            time.sleep(3)
        else: raise RuntimeError("Kafka UI did not become ready")
        try:
            with opener.open(url + "/api/clusters", timeout=5) as response:
                assert "/login" in response.url or "application/json" not in response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            assert error.code in (401, 403)
        login = urllib.parse.urlencode({"username": "kafka_viewer", "password": passwords["browser"]}).encode()
        with opener.open(urllib.request.Request(url + "/login", data=login), timeout=10) as response:
            response.read()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            with opener.open(url + "/api/clusters", timeout=15) as response:
                clusters = json.load(response)
            if clusters and clusters[0].get("status") == "online": break
            if clusters and str(clusters[0].get("status")).upper() == "ONLINE": break
            time.sleep(3)
        else: raise RuntimeError("UI login succeeded but Kafka cluster remained offline")
        with opener.open(url + "/api/clusters/brokecart/topics", timeout=15) as response:
            payload = response.read().decode()
        assert "inventory.commands" in payload
        print("PASS: read-only UI starts with a read-only filesystem, requires browser login, and lists Kafka topics over TLS", flush=True)

        run(["docker", "stop", "-t", "20", containers[2]], timeout=45)
        produce("inventory.commands", "orders", "brokecart-fixture-after-failure")
        print("PASS: acks=all writes continue after one combined broker/controller stops", flush=True)
        print("PASS: Kafka runtime verification completed; cleaning disposable fixtures", flush=True)
    except Exception:
        for name in containers:
            result = subprocess.run(["docker", "logs", "--tail", "12", name], text=True, capture_output=True)
            print(f"Fixture diagnostic {name}:\n{result.stdout}{result.stderr}", flush=True)
        raise
    finally:
        for name in reversed(containers):
            owned = subprocess.run(["docker", "inspect", "--format", '{{ index .Config.Labels "brokecart.kafka-check" }}', name],
                                   text=True, capture_output=True)
            if owned.returncode == 0 and owned.stdout.strip() == prefix:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        if network_created:
            subprocess.run(["docker", "network", "rm", prefix], capture_output=True)
        shutil.rmtree(workspace)


if __name__ == "__main__":
    main()
