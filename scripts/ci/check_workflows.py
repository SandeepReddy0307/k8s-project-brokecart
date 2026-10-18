#!/usr/bin/env python3
"""Validate GitHub Actions syntax and context availability with pinned actionlint."""
import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

VERSION = "1.7.12"
SHA256 = "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--download", action="store_true", help="download the verified Linux x64 release if needed")
parser.add_argument("--binary", help="use an existing actionlint binary")
args = parser.parse_args()
binary = args.binary or shutil.which("actionlint")
if binary:
    subprocess.run([binary, "-shellcheck=", "-pyflakes="], cwd=ROOT, check=True)
elif args.download:
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        parser.error("automatic installation supports the configured Linux x64 runner only")
    with tempfile.TemporaryDirectory(prefix="brokecart-actionlint-") as directory:
        archive = Path(directory) / "actionlint.tar.gz"
        url = f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/actionlint_{VERSION}_linux_amd64.tar.gz"
        with urllib.request.urlopen(url, timeout=30) as response:
            archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise SystemExit("actionlint archive checksum mismatch")
        with tarfile.open(archive) as package:
            member = package.getmember("actionlint")
            if not member.isfile():
                raise SystemExit("Unexpected actionlint archive entry")
            binary = Path(directory) / "actionlint"
            binary.write_bytes(package.extractfile(member).read())
        binary.chmod(0o700)
        subprocess.run([str(binary), "-shellcheck=", "-pyflakes="], cwd=ROOT, check=True)
else:
    parser.error("install actionlint or pass --download")
print("PASS: actionlint workflow syntax and context checks")
