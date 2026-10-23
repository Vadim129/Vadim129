#!/usr/bin/env python3
"""Apply the ONE permanent APK signing identity. Never generates/replaces a key.

Private .signing/ is restored from the owner's private backup when necessary.
CI artifacts use a throwaway test identity; they must pass through this script
before delivery. No passwords/keys are accepted in command-line arguments.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12

ROOT = Path(__file__).resolve().parents[1]


def java_command():
    if os.environ.get("JAVA_HOME"):
        return str(Path(os.environ["JAVA_HOME"]) / "bin/java")
    if shutil.which("java"):
        return shutil.which("java")
    import jdk4py
    return str(jdk4py.JAVA)


def contents(path):
    # Signing must never alter manifest, code, native libraries, or resources.
    with zipfile.ZipFile(path) as apk:
        assert apk.testzip() is None, "Corrupt APK ZIP"
        return {i.filename: hashlib.sha256(apk.read(i)).hexdigest()
                for i in apk.infolist()
                if not re.match(r"META-INF/[^/]+\.(SF|RSA|DSA|EC)$", i.filename, re.I)
                and i.filename.upper() != "META-INF/MANIFEST.MF"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "payload/mastr-studio-ci.apk")
    parser.add_argument("--output", type=Path, default=ROOT / "payload/mastr-studio.apk")
    args = parser.parse_args()
    private = ROOT / ".signing"
    config_path = private / "signing.json"
    if not config_path.is_file():
        raise SystemExit("Permanent key missing. Restore the PRIVATE signing backup to .signing/. DO NOT generate a replacement key.")
    config = json.loads(config_path.read_text())
    expected = json.loads((ROOT / "mastering-app/signing-certificate.json").read_text())["certificate_sha256"]
    store = private / config["keystore"]
    password = config["password"]
    _, certificate, _ = pkcs12.load_key_and_certificates(store.read_bytes(), password.encode())
    actual = certificate.fingerprint(hashes.SHA256()).hex()
    if actual != expected or actual != config["certificate_sha256"]:
        raise SystemExit("Wrong keystore: certificate does not match the permanent application identity")
    # Also check that the public PEM and pinned fingerprint agree.
    public = x509.load_pem_x509_certificate((ROOT / "mastering-app/signing-certificate.pem").read_bytes())
    assert public.fingerprint(hashes.SHA256()).hex() == expected
    jar = ROOT / "payload/android-apksigner.jar"
    pinned = (ROOT / "payload/android-apksigner-sha256.txt").read_text().split()[0]
    assert hashlib.sha256(jar.read_bytes()).hexdigest() == pinned, "Changed apksigner tool"
    assert args.input.is_file(), "Input APK missing"
    original = contents(args.input)
    env = dict(os.environ, MASTR_SIGNING_PASSWORD=password)
    java = java_command()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".mastr-signed-", suffix=".apk", dir=args.output.parent)
    os.close(fd)
    temporary = Path(temporary)
    try:
        subprocess.run([java, "-jar", str(jar), "sign", "--ks", str(store),
                        "--ks-type", "PKCS12", "--ks-key-alias", config["alias"],
                        "--ks-pass", "env:MASTR_SIGNING_PASSWORD", "--key-pass", "env:MASTR_SIGNING_PASSWORD",
                        "--v1-signing-enabled", "false", "--v2-signing-enabled", "true",
                        "--v3-signing-enabled", "true", "--v4-signing-enabled", "false",
                        "--out", str(temporary), str(args.input)],
                       env=env, check=True, capture_output=True)
        verification = subprocess.check_output(
            [java, "-jar", str(jar), "verify", "--verbose", "--print-certs", str(temporary)],
            text=True, stderr=subprocess.DEVNULL)
        fingerprints = re.findall(r"certificate SHA-256 digest: ([0-9a-f]+)", verification)
        assert fingerprints and set(fingerprints) == {expected}, "Unexpected APK signer"
        assert contents(temporary) == original, "APK contents changed during signing"
        os.replace(temporary, args.output)
        report = {"certificate_sha256": expected,
                  "apk_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                  "apk_bytes": args.output.stat().st_size,
                  "unchanged_app_contents": True,
                  "verification": verification}
        (ROOT / "payload/mastr-signature.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Signed and verified with permanent certificate:", expected)
        print("App contents unchanged. APK:", args.output)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
