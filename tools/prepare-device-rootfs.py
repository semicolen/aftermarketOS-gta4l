"""Prepare a headless SM-T505 boot-test rootfs using verified local inputs."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))
from debport.android_boot import BootImage, read_newc
from debport.build import output_path, write


def run(*command):
    print("+ " + " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--hardware", type=Path, required=True)
    p.add_argument("--boot", type=Path, required=True)
    p.add_argument("--public-key", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--base-sha256", default="9c003bbd26169c9d18e2da302c049d3cfebb602c50061c2e1bf25528f277a04d",
                   help="explicit verified base tarball hash for a rebuilt Debian base")
    a = p.parse_args()
    if os.geteuid() != 0:
        raise ValueError("Linux root required")
    output = output_path(a.output)
    key = a.public_key.read_text().strip()
    if not key.startswith("ssh-ed25519 ") or "\n" in key:
        raise ValueError("expected one dedicated Ed25519 public key")
    with a.base.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != a.base_sha256:
            raise ValueError("base tarball differs from the verified first build")
    with a.hardware.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != "4d3ae5a04f72c2d41feade4f47d834e70e0ed3688e82634ca02f6ea389972ad8":
            raise ValueError("hardware archive differs from the read-only device export")
    boot = BootImage.parse(a.boot.read_bytes())
    records = {name: (payload, fields) for name, payload, fields, _ in read_newc(gzip.decompress(boot.ramdisk))}
    output.mkdir()
    root = output / "rootfs"
    root.mkdir()
    run("tar", "--numeric-owner", "--xattrs", "--acls", "-xJf", a.base, "-C", root)
    with tarfile.open(a.hardware) as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not (
                member.name.startswith("usr/lib/modules/4.19.300-perf") or
                member.name.startswith("usr/lib/firmware/postmarketos")
            ) or not (member.isfile() or member.isdir()):
                raise ValueError("unexpected hardware archive member")
        archive.extractall(root, filter="data")
    modules = list((root / "usr/lib/modules/4.19.300-perf").rglob("*.ko"))
    if len(modules) != 37:
        raise ValueError("expected 37 matching kernel modules")
    private = root / "usr/lib/debport-init"
    private.mkdir()
    for name in ("usr/bin/unudhcpd", "usr/lib/ld-musl-aarch64.so.1", "usr/lib/libc.musl-aarch64.so.1"):
        payload, fields = records[name]
        target = private / Path(name).name
        if fields[1] & 0o170000 == 0o120000:
            destination = payload.decode()
            if "/" in destination:
                raise ValueError("unexpected private runtime symlink")
            target.symlink_to(destination)
        else:
            target.write_bytes(payload)
            target.chmod(0o755)
    run("chroot", root, "/usr/lib/debport-init/ld-musl-aarch64.so.1", "--list", "/usr/lib/debport-init/unudhcpd")
    run("chroot", root, "depmod", "-a", "4.19.300-perf")
    run("chroot", root, "useradd", "--create-home", "--shell", "/bin/bash", "--groups", "adm,systemd-journal", "debian")
    write(root, "home/debian/.ssh/authorized_keys", key + "\n")
    (root / "home/debian/.ssh").chmod(0o700)
    (root / "home/debian/.ssh/authorized_keys").chmod(0o600)
    run("chroot", root, "chown", "-R", "debian:debian", "/home/debian/.ssh")
    write(root, "etc/ssh/sshd_config.d/10-debport.conf", "PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n")
    write(root, "etc/systemd/system/ssh.service.d/10-first-boot.conf", "[Service]\nExecStartPre=\nExecStartPre=/usr/bin/ssh-keygen -A\nExecStartPre=/usr/sbin/sshd -t\n")
    for unit in ("ssh.service", "ssh.socket"):
        (root / "etc/systemd/system" / unit).unlink(missing_ok=True)
    wanted = root / "etc/systemd/system/multi-user.target.wants"
    wanted.mkdir(exist_ok=True)
    ssh_wanted = wanted / "ssh.service"
    ssh_wanted.unlink(missing_ok=True)
    ssh_wanted.symlink_to("/usr/lib/systemd/system/ssh.service")
    repo = Path(__file__).resolve().parents[1]
    write(root, "usr/local/sbin/debport-usb-network", (repo / "boot/debport-usb-network.sh").read_text())
    (root / "usr/local/sbin/debport-usb-network").chmod(0o755)
    write(root, "etc/systemd/system/debport-usb-network.service", (
        "[Unit]\nDescription=Debport USB network and DHCP\nAfter=systemd-udev-trigger.service\nBefore=ssh.service\n"
        "[Service]\nType=simple\nExecStart=/usr/local/sbin/debport-usb-network\nRestart=on-failure\nRestartSec=3\n"
        "[Install]\nWantedBy=multi-user.target\n"
    ))
    (wanted / "debport-usb-network.service").symlink_to("/etc/systemd/system/debport-usb-network.service")
    write(root, "etc/fstab", "LABEL=debport-test / ext4 defaults,noatime 0 0\n")
    write(root, "etc/motd", "Debian SM-T505 boot test. USB SSH only; desktop/hardware integration is pending.\n")
    write(root, "etc/issue", "Debian 13 SM-T505 boot test - USB SSH: debian@172.16.42.1\n")
    journal = root / "var/log/journal"
    journal.mkdir(exist_ok=True)
    journal.chmod(0o2755)
    run("chroot", root, "chown", "root:systemd-journal", "/var/log/journal")
    identity = {"device": "samsung-gta4l", "status": "device-boot-test", "hardware_tested": False,
                "ssh": "dedicated-public-key-only", "root_password": "locked", "desktop": "none"}
    write(root, "etc/debport-image.json", json.dumps(identity, indent=2) + "\n")
    write(root, "etc/systemd/system/default.target", "")
    (root / "etc/systemd/system/default.target").unlink()
    (root / "etc/systemd/system/default.target").symlink_to("/usr/lib/systemd/system/multi-user.target")
    run("chroot", root, "dpkg", "--audit")
    run("chroot", root, "/lib/systemd/systemd", "--version")
    run("chroot", root, "systemd-analyze", "--man=no", "verify", "debport-usb-network.service", "ssh.service")
    image = output / "rootfs.ext4"
    with image.open("xb") as stream:
        # Stay below Python ZIP64 and older recovery unzip signed-size limits.
        stream.truncate(1536 * 1024 * 1024)
    run("mke2fs", "-q", "-t", "ext4", "-F", "-b", "4096", "-L", "debport-test", "-U", str(uuid.uuid4()),
        "-O", "^orphan_file,^metadata_csum_seed", "-d", root, image)
    run("e2fsck", "-f", "-n", image)
    with image.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (output / "rootfs-manifest.json").write_text(json.dumps({"image_sha256": digest, "identity": identity,
        "modules": len(modules), "kernel": "4.19.300-perf #11-postmarketOS", "device_boot_tested": False}, indent=2) + "\n")
    print(json.dumps({"output": str(output), "rootfs_sha256": digest, "modules": len(modules)}))


if __name__ == "__main__":
    main()
