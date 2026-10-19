"""Install the device package, validate GNOME, and create a separate 6 GiB image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))
from debport.build import write
from gta4l import account as gnome_account


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--credentials", type=Path,
                        help="optional export of the fixed login defaults; existing different credentials are refused")
    parser.add_argument("--compat-package", type=Path,
                        help="Linux 4.19 build of Debian bubblewrap (defaults to the work directory)")
    args = parser.parse_args()
    root = args.work.resolve() / "rootfs"
    package = args.work.resolve() / "debport-gta4l-gnome_0.1.4_arm64.deb"
    if os.geteuid() != 0 or not package.is_file():
        raise ValueError("Linux root and the assembled device package are required")
    compat_package = args.compat_package or args.work.resolve() / "bubblewrap_0.12.0-1~deb13u1+debport1_arm64.deb"
    if not compat_package.is_file():
        raise ValueError("the older-kernel bubblewrap package is required")
    environment = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C.UTF-8"}

    def run(*command, **kwargs):
        print("+ " + " ".join(map(str, command)), flush=True)
        return subprocess.run(list(map(str, command)), check=True, env=environment, **kwargs)

    def chroot(*command, **kwargs):
        return run("chroot", root, *command, **kwargs)

    target = root / "tmp/debport-bubblewrap.deb"
    target.write_bytes(compat_package.read_bytes())
    chroot("dpkg", "-i", "/tmp/debport-bubblewrap.deb")
    target.unlink()
    target = root / "tmp/debport-device.deb"
    target.write_bytes(package.read_bytes())
    chroot("dpkg", "-i", "/tmp/debport-device.deb")
    target.unlink()
    # PulseAudio remains the audio server; PipeWire/WirePlumber carry cameras.
    pulse = root / "etc/pulse/default.pa"
    if ".include /etc/pulse/default.pa.d" not in pulse.read_text():
        pulse.write_text(pulse.read_text() + "\n.include /etc/pulse/default.pa.d\n")
    write(root, "etc/environment", "LIBGL_ALWAYS_SOFTWARE=1\nGALLIUM_DRIVER=llvmpipe\nGSK_RENDERER=gl\n")
    credentials = {"username": gnome_account.USERNAME, "password": gnome_account.PASSWORD,
                   "purpose": "Local GNOME login and sudo", "source": gnome_account.DEFAULTS_SOURCE}
    if args.credentials:
        if args.credentials.exists() and json.loads(args.credentials.read_text()) != credentials:
            raise ValueError("refusing to overwrite credentials for an existing installation")
        args.credentials.parent.mkdir(parents=True, exist_ok=True)
        args.credentials.write_text(json.dumps(credentials, indent=2) + "\n")
        args.credentials.chmod(0o600)
    gnome_account.configure(root, chroot)
    chroot("passwd", "-l", "root")
    login_verification = gnome_account.verify(root)
    (args.work / "login-defaults.json").write_text(json.dumps(credentials, indent=2) + "\n")
    (args.work / "login-verification.json").write_text(json.dumps(login_verification, indent=2) + "\n")
    write(root, "etc/fstab", "LABEL=debport-gnome / ext4 defaults,noatime 0 0\n")
    write(root, "etc/dconf/db/local.d/10-gta4l", "[org/gnome/desktop/session]\nidle-delay=uint32 0\n")
    write(root, "etc/dconf/profile/user", "user-db:user\nsystem-db:local\n")
    chroot("dconf", "update")
    identity = {"device": "samsung-gta4l", "status": "gnome-device-preview", "desktop": "gnome",
                "hardware_tested": False, "headless_predecessor_boot_verified": True,
                "ssh": "dedicated-public-key-only", "root_password": "locked",
                "local_login": "postmarketos-prebuilt-defaults", "username": gnome_account.USERNAME,
                "auto_login": gnome_account.USERNAME, "login_defaults_source": gnome_account.DEFAULTS_SOURCE}
    write(root, "etc/debport-image.json", json.dumps(identity, indent=2) + "\n")
    chroot("depmod", "-a", "4.19.300-perf")
    chroot("dpkg", "--audit")
    if not (root / "usr/share/alsa/ucm2/ucm.conf").is_file():
        raise ValueError("ALSA's base UCM configuration is missing")
    chroot("bwrap", "--version")
    chroot("gnome-shell", "--version")
    chroot("/usr/lib/debport-device/sbin/ModemManager", "--version")
    for binary in ("/usr/lib/gta4l-kgsl/libvulkan_freedreno.so", "/usr/lib/gta4l-zink/lib/libEGL.so.1",
                   "/usr/lib/debport-gnome-settings/bin/gnome-control-center", "/usr/lib/debport-device/libexec/iio-sensor-proxy"):
        chroot("/lib/ld-linux-aarch64.so.1", "--library-path", "/usr/lib/gta4l-zink/lib:/usr/lib/debport-device/lib", "--list", binary)
    chroot("env", "LD_LIBRARY_PATH=/usr/lib/debport-device/lib", "PD_MAPPER_FW_DIR=/lib/firmware/postmarketos",
           "/usr/lib/debport-device/bin/pd-mapper", "--check-maps")
    units = [path.name for path in (root / "etc/systemd/system").glob("gta4l-*.service")]
    chroot("systemd-analyze", "--man=no", "verify", *units, "ModemManager.service", "iio-sensor-proxy.service", "gdm3.service")
    (root / "usr/sbin/policy-rc.d").unlink(missing_ok=True)
    (root / "etc/machine-id").unlink(missing_ok=True)
    for key in (root / "etc/ssh").glob("ssh_host_*"):
        key.unlink()
    with (args.work / "packages-final.tsv").open("w") as stream:
        chroot("dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n", stdout=stream)
    image = args.work / "rootfs.ext4"
    with image.open("xb") as stream:
        stream.truncate(6 * 1024 * 1024 * 1024)
    run("mke2fs", "-q", "-t", "ext4", "-F", "-b", "4096", "-L", "debport-gnome", "-U", str(uuid.uuid4()),
        "-O", "^orphan_file,^metadata_csum_seed", "-d", root, image)
    run("e2fsck", "-f", "-n", image)
    with image.open("rb") as stream:
        image_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {"image_sha256": image_sha, "image_bytes": image.stat().st_size, "identity": identity,
                "kernel": "4.19.300-perf #11-postmarketOS", "modules": 37,
                "device_boot_tested": False, "device_package": package.name,
                "device_package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
                "bubblewrap_compat_package": compat_package.name,
                "bubblewrap_compat_sha256": hashlib.sha256(compat_package.read_bytes()).hexdigest(),
                "login_verification": login_verification}
    (args.work / "rootfs-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
