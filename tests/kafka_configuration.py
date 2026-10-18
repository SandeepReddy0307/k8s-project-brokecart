"""Validate Kafka/Kafbat configuration without contacting Kubernetes or OpenBao."""
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(chart, namespace):
    output = subprocess.check_output(
        ["helm", "template", chart, str(ROOT / "infra/charts" / chart),
         "--namespace", namespace], text=True)
    return [r for r in yaml.safe_load_all(output) if r]


def resource(resources, kind, name):
    return next(r for r in resources
                if r["kind"] == kind and r["metadata"]["name"] == name)


def check():
    values = yaml.safe_load((ROOT / "infra/charts/kafka/values.yaml").read_text())
    kafka = render("kafka", "brokecart-kafka")
    ui = render("kafka-ui", "brokecart-kafka-ui")
    statefulset = resource(kafka, "StatefulSet", "kafka")
    pod = statefulset["spec"]["template"]["spec"]
    broker = pod["containers"][0]
    assert statefulset["spec"]["replicas"] == 3
    assert statefulset["spec"]["podManagementPolicy"] == "Parallel"
    assert pod["automountServiceAccountToken"] is False
    assert broker["command"] == ["/bin/bash", "/scripts/start-kafka.sh"]
    assert "args" not in broker
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert {m["name"] for m in broker["volumeMounts"]} == set(volumes) | {"data"}
    assert volumes["tls"]["secret"]["secretName"] == values["tls"]["secretName"]
    assert len([v for v in volumes if v.startswith("client-")]) == 15
    assert len([r for r in kafka if r["kind"] == "ExternalSecret"]) == 16
    assert resource(kafka, "PodDisruptionBudget", "kafka")["spec"]["minAvailable"] == 2
    certificate = resource(kafka, "Certificate", "kafka")["spec"]
    assert all(f"kafka-{i}.kafka-headless.brokecart-kafka.svc.cluster.local"
               in certificate["dnsNames"] for i in range(3))
    assert certificate["keystores"]["pkcs12"]["profile"] == "Modern2023"

    cm = resource(kafka, "ConfigMap", "kafka-topic-provisioning")
    job = resource(kafka, "Job", "kafka-topic-provisioning")
    command = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
    assert command.index("/scripts/create-topics.sh") < command.index("/scripts/apply-acls.sh")
    assert '--command-config "$CLIENT_CONFIG"' in command
    assert '--command-config "$CLIENT_CONFIG"' in cm["data"]["create-topics.sh"]
    for r in kafka:
        if r["kind"] == "ConfigMap":
            for name, script in r["data"].items():
                if name.endswith(".sh"):
                    subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    for script in (ROOT / "infra/bootstrap").glob("*kafka*.sh"):
        subprocess.run(["bash", "-n", str(script)], check=True)

    deployment = resource(ui, "Deployment", "kafka-ui")
    ui_pod = deployment["spec"]["template"]["spec"]
    ui_container = ui_pod["containers"][0]
    assert ui_container["securityContext"]["readOnlyRootFilesystem"] is True
    assert resource(ui, "ServiceAccount", "kafka-ui")["automountServiceAccountToken"] is False
    config = yaml.safe_load(resource(ui, "ConfigMap", "kafka-ui-fromvalues")["data"]["config.yml"])
    cluster = config["kafka"]["clusters"][0]
    assert cluster["readOnly"] is True
    assert cluster["properties"]["security.protocol"] == "SASL_SSL"
    assert cluster["properties"]["ssl.endpoint.identification.algorithm"] == "https"
    assert cluster["properties"]["sasl.jaas.config"] == "${KAFKA_SASL_JAAS_CONFIG}"
    env = {e["name"]: e for e in ui_container["env"]}
    assert env["KAFKA_SASL_JAAS_CONFIG"]["valueFrom"]["secretKeyRef"]["name"] == "kafka-ui-client"
    route = resource(ui, "HTTPRoute", "kafka-ui")["spec"]
    assert route["hostnames"] == ["kafka.brokecart.com"]
    assert route["parentRefs"][0]["sectionName"] == "https"
    assert not any(v.get("secret", {}).get("secretName") == "kafka-broker-auth"
                   for v in ui_pod["volumes"])
    assert all("admin" not in d["remoteRef"]["key"]
               for r in ui if r["kind"] == "ExternalSecret" for d in r["spec"]["data"])

    # Exercise the generated grant script against an argument-capturing CLI.
    with tempfile.TemporaryDirectory(prefix="brokecart-acl-") as directory:
        work = Path(directory)
        stub = work / "kafka-acls"
        stub.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                        'with open(os.environ["ACL_CAPTURE"],"a") as f: '
                        'f.write(json.dumps(sys.argv[1:])+"\\n")\n')
        stub.chmod(0o700)
        capture = work / "calls.jsonl"
        script = cm["data"]["apply-acls.sh"].replace("/opt/kafka/bin/kafka-acls.sh", str(stub))
        env = {**os.environ, "BOOTSTRAP_SERVERS": "test:9092", "CLIENT_CONFIG": "/tmp/test.properties",
               "ACL_CAPTURE": str(capture)}
        subprocess.run(["bash"], input=script, text=True, env=env, check=True, capture_output=True)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        grants = set()
        for args in calls:
            def flag(name):
                return args[args.index(name) + 1]
            assert flag("--command-config") == "/tmp/test.properties"
            assert "--add" in args and "--remove" not in args
            principal = flag("--allow-principal")
            kind = next((k for k in ("topic", "group") if "--" + k in args), "cluster")
            target = flag("--" + kind) if kind != "cluster" else ""
            if kind != "cluster":
                assert flag("--resource-pattern-type") == "literal"
            for index, arg in enumerate(args):
                if arg == "--operation":
                    grants.add((principal, kind, target, args[index + 1]))
        expected = set()
        for service, permissions in values["acls"]["services"].items():
            principal = "User:brokecart_" + service.replace("-", "_")
            expected.add((principal, "cluster", "", "IdempotentWrite"))
            for topic in permissions["produces"]:
                expected.add((principal, "topic", topic, "Write"))
            if permissions["consumes"]:
                expected.add((principal, "group", permissions["group"], "Read"))
            for topic in permissions["consumes"]:
                expected.add((principal, "topic", topic, "Read"))
                expected.add((principal, "topic", topic + ".DLT", "Write"))
        principal = "User:" + values["acls"]["ui"]["username"]
        expected.update([(principal, "cluster", "", "Describe"),
                         (principal, "cluster", "", "DescribeConfigs"),
                         (principal, "group", "*", "Describe")])
        for topic in values["topics"]["names"]:
            for name in (topic, topic + ".DLT"):
                for operation in ("Read", "DescribeConfigs"):
                    expected.add((principal, "topic", name, operation))
        assert grants == expected, (grants - expected, expected - grants)
        assert not any(p == principal and op in {"Write", "Create", "Alter", "Delete", "IdempotentWrite"}
                       for p, _, _, op in grants)

        # Ensure credentials become a private runtime file and malformed users are rejected.
        auth = work / "auth"; tls = work / "tls"
        auth.mkdir(); tls.mkdir()
        (auth / "admin-username").write_text("kafka_admin")
        (auth / "admin-password").write_text("abc123" * 8)
        (auth / "keystore-password").write_text("def456" * 8)
        (tls / "truststore.p12").write_bytes(b"synthetic fixture")
        client = work / "client.properties"
        env.update(KAFKA_AUTH_DIR=str(auth), KAFKA_TLS_DIR=str(tls), CLIENT_CONFIG=str(client))
        helper = ROOT / "infra/charts/kafka/files/admin-client.sh"
        subprocess.run(["bash", "-ec", 'source "$1"', "check", str(helper)], env=env, check=True)
        assert stat.S_IMODE(client.stat().st_mode) == 0o600
        assert "ssl.endpoint.identification.algorithm=https" in client.read_text()
        (auth / "admin-username").write_text('bad"user')
        bad = subprocess.run(["bash", "-ec", 'source "$1"', "check", str(helper)],
                             env=env, capture_output=True)
        assert bad.returncode != 0

    for override in ["replicaCount=2", "topics.replicationFactor=4", "topics.minInSyncReplicas=4",
                     "topics.partitions=0", "kraft.clusterId=bad"]:
        result = subprocess.run(["helm", "template", "kafka", str(ROOT / "infra/charts/kafka"),
                                 "--set", override], capture_output=True)
        assert result.returncode != 0, override
    print("PASS: Kafka/UI rendering, mounts, TLS, scoped Secrets, exact ACLs, private client config, and invalid-topology rejection")


if __name__ == "__main__":
    check()
