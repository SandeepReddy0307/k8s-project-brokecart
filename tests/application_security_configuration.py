"""Offline test: real RSA generation, fake OpenBao transport, chart access boundaries."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
def render(*extra):
    text = subprocess.check_output(["helm", "template", "catalog", "infra/charts/application",
        "-n", "brokecart-catalog", "-f", "infra/values/catalog.yaml", *extra], cwd=ROOT, text=True)
    return [r for r in yaml.safe_load_all(text) if r]
resources = render()
es = next(r for r in resources if r["kind"] == "ExternalSecret"
          and r["metadata"]["name"] == "catalog-application-security")
assert {d["secretKey"] for d in es["spec"]["data"]} == {"internal-token", "jwt-public-key"}
assert all("identity/jwt" not in d["remoteRef"]["key"] for d in es["spec"]["data"])
identity = render("--set", "security.identitySigningKey=true")
assert any(d["secretKey"] == "jwt-private-key" for r in identity if r["kind"] == "ExternalSecret"
           and r["metadata"]["name"] == "catalog-application-security" for d in r["spec"]["data"])
assert not any(r["metadata"]["name"] == "catalog-application-security"
               for r in render("--set", "security.enabled=false", "--set", "deployment.enabled=false"))

stub = r'''#!/usr/bin/env python3
import json,os,secrets,sys
from pathlib import Path
p=Path(os.environ["FAKE_BAO_STATE"])
state=json.loads(p.read_text()) if p.exists() else {"kv":{},"policies":{},"roles":{}}
args=sys.argv[1:]
def save():
    p.write_text(json.dumps(state));p.chmod(0o600)
if os.environ.get("BAO_TOKEN") != "offline-test-token":sys.exit(1)
if args[:2]==["token","lookup"]:print("[root]")
elif args[:2]==["kv","get"]:
    key=args[-1]
    if key not in state["kv"]:sys.exit(2)
    field=next((x.split("=",1)[1] for x in args if x.startswith("-field=")),None)
    if field:
        if field not in state["kv"][key]:sys.exit(2)
        print(state["kv"][key][field],end="")
    else:print(json.dumps(state["kv"][key]))
elif args[:2]==["kv","put"]:
    rest=[a for a in args[2:] if not a.startswith("-") or a=="-"]
    key=rest[0]
    if key in state["kv"]:sys.exit(3)
    if rest[1:]==["-"]:data=json.load(sys.stdin)
    else:
        data={}
        for pair in rest[1:]:
            k,v=pair.split("=",1);data[k]=sys.stdin.read() if v=="-" else v
    state["kv"][key]=data;save()
elif args[:2]==["policy","write"]:
    state["policies"][args[2]]=sys.stdin.read();save()
elif args[0]=="write" and args[1]=="-field=random_bytes":
    print(secrets.token_hex(32))
elif args[0]=="write" and args[1].startswith("auth/kubernetes/role/"):
    state["roles"][args[1].split("/")[-1]]=dict(x.split("=",1) for x in args[2:]);save()
else:sys.exit(4)
'''
with tempfile.TemporaryDirectory(prefix="brokecart-security-check-") as directory:
    work = Path(directory)
    (work / "bao").write_text(stub)
    (work / "bao").chmod(0o700)
    (work / "kubectl").write_text("#!/usr/bin/env python3\nimport os,sys\nos.execv('/bin/sh',['/bin/sh','-c',sys.argv[-1]])\n")
    (work / "kubectl").chmod(0o700)
    env = {**os.environ, "PATH": str(work) + os.pathsep + os.environ["PATH"],
           "FAKE_BAO_STATE": str(work / "state.json")}
    command = ["bash", "infra/bootstrap/run-application-security-bootstrap.sh"]
    for _ in range(2):
        result = subprocess.run(command, cwd=ROOT, env=env, input="offline-test-token\n",
                                text=True, capture_output=True, check=True)
        state = json.loads((work / "state.json").read_text())
        if _ == 0:
            original = state["kv"]
        else:
            assert original == state["kv"], "Rerun rotated existing security credentials"
        assert "BEGIN PRIVATE KEY" not in result.stdout + result.stderr
    pair = state["kv"]["brokecart/identity/jwt"]
    derived = subprocess.check_output(["openssl", "pkey", "-pubout"],
                                     input=pair["private-key"], text=True)
    assert derived.strip() == pair["public-key"].strip()
    assert derived.strip() == state["kv"]["brokecart/shared/jwt"]["public-key"].strip()
    token = state["kv"]["brokecart/shared/internal"]["token"]
    assert len(token) == 64 and token.strip() == token
    assert len(state["roles"]) == 15
    maintenance = state["roles"]["maintenance-application-secrets"]
    assert maintenance["policies"] == "maintenance-internal-reader"
    assert maintenance["bound_service_account_namespaces"] == "brokecart-maintenance"
    assert "identity/jwt" not in state["policies"]["maintenance-internal-reader"]
    assert "shared/jwt" not in state["policies"]["maintenance-internal-reader"]
    for role, settings in state["roles"].items():
        if role == "maintenance-application-secrets":
            continue
        if role == "identity-application-secrets":
            assert "identity-signing-key-reader" in settings["policies"]
        else:
            assert settings["policies"] == "application-security-reader"
        service = role.removesuffix("-application-secrets")
        assert settings["bound_service_account_namespaces"] == "brokecart-" + service
        assert settings["bound_service_account_names"] == role
        assert settings["audience"] == "vault"
    # Refuse a mismatched published key rather than silently rotating tokens.
    state["kv"]["brokecart/shared/jwt"]["public-key"] = "mismatched-key"
    (work / "state.json").write_text(json.dumps(state))
    result = subprocess.run(command, cwd=ROOT, env=env, input="offline-test-token\n",
                            text=True, capture_output=True)
    assert result.returncode != 0
    assert "disagree" in result.stderr
print("PASS: RSA keys, preserved credentials, 14 backend roles, maintenance token-only role and catalog private-key exclusion")
