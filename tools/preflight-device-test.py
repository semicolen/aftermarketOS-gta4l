"""Read-only recovery preflight for the generated SM-T505 boot-test ZIP."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--serial", required=True)
    p.add_argument("--directory", type=Path, required=True)
    a = p.parse_args()
    manifest = json.loads((a.directory / "manifest.json").read_text())
    archive = a.directory / manifest["installer"]
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != manifest["installer_sha256"]:
        raise ValueError("installer changed")
    adb = ["adb", "-s", a.serial]

    def capture(command):
        return subprocess.check_output(adb + ["shell", command], text=True).strip()

    if capture("getprop ro.product.device") != "gta4l" or capture("id -u") != "0":
        raise ValueError("expected SM-T505 root recovery")
    print(capture("df -k /tmp"), flush=True)
    subprocess.run(adb + ["push", str(archive), "/tmp/debport-test.zip"], check=True)
    subprocess.run(adb + ["push", str(a.directory / "install.sh"), "/tmp/debport-install.sh"], check=True)
    if capture("sha256sum /tmp/debport-test.zip").split()[0] != digest:
        raise ValueError("uploaded ZIP hash mismatch")
    print("Checking recovery ZIP extraction and rootfs checksum without writing a file...", flush=True)
    rootfs_digest = capture("unzip -p /tmp/debport-test.zip rootfs.ext4 | sha256sum").split()[0]
    if rootfs_digest != manifest["rootfs"]["image_sha256"]:
        raise ValueError("recovery cannot correctly extract the rootfs from this ZIP")
    print("Recovery rootfs extraction/checksum passed", flush=True)
    result = capture("DEBPORT_PREFLIGHT_ONLY=1 sh /tmp/debport-install.sh 3 3 /tmp/debport-test.zip 3>/tmp/debport-preflight-ui.log; result=$?; cat /tmp/debport-preflight-ui.log; cat /tmp/debport-install/existing-root-fsck.log; exit $result")
    if "Read-only Debian installer preflight passed" not in result:
        raise ValueError("installer preflight did not confirm success")
    print(result, flush=True)
    report = {"serial": a.serial, "read_only_preflight": "passed", "installer_sha256": digest,
              "recovery_rootfs_extraction_sha256": rootfs_digest, "installer_preflight_output": result,
              "device_partitions_written": False, "debian_installed": False}
    (a.directory / "preflight.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
