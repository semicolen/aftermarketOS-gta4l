"""Prepare Debian GNOME userspace; device adaptation is a separate stage."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))
from debport.build import output_path, write
from gta4l.account import USERNAME

PACKAGES = (
    "gdm3", "gnome-shell", "gnome-session", "gnome-control-center",
    "gnome-keyring", "gnome-terminal", "nautilus", "gnome-calculator",
    "gnome-text-editor", "gnome-system-monitor", "gnome-disk-utility",
    "gnome-backgrounds", "gnome-logs", "loupe", "gnome-software",
    "fonts-cantarell", "fonts-dejavu-core", "pipewire", "wireplumber",
    "network-manager", "wpasupplicant", "wireless-regdb", "bluez", "pulseaudio",
    "pulseaudio-module-bluetooth", "alsa-utils", "alsa-ucm-conf", "mesa-utils", "vulkan-tools",
    "python3-gi", "python3-dbus", "gir1.2-gtk-3.0", "qrtr-tools",
    "rmtfs", "tqftpserv", "iio-sensor-proxy", "modemmanager", "geoclue-2.0",
    "wayland-utils", "e2fsprogs", "ca-certificates", "curl", "locales", "sudo", "libprotobuf-c1",
    "libpam-gnome-keyring", "gnome-maps", "systemd-timesyncd", "libqmi-utils",
    "gnome-snapshot", "zram-tools",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or sys.platform != "linux":
        raise ValueError("Linux root is required")
    output = output_path(args.output)
    base = args.prepared_base.resolve()
    identity = json.loads((base / "etc/debport-image.json").read_text())
    if identity["device"] != "samsung-gta4l" or identity["desktop"] != "none":
        raise ValueError("expected the prepared SM-T505 headless base")
    output.mkdir()
    root = output / "rootfs"
    root.mkdir()
    subprocess.run(["cp", "-a", str(base) + "/.", str(root)], check=True)
    write(root, "usr/sbin/policy-rc.d", "#!/bin/sh\nexit 101\n")
    (root / "usr/sbin/policy-rc.d").chmod(0o755)
    shutil.copyfile("/etc/resolv.conf", root / "etc/resolv.conf")
    mounted = []
    manifest = {"stage": "installing-userspace", "packages_requested": PACKAGES,
                "desktop": "gnome", "hardware_tested": False}
    receipt = output / "userspace-manifest.json"
    environment = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C.UTF-8"}

    def run(*command):
        print("+ " + " ".join(map(str, command)), flush=True)
        subprocess.run(list(map(str, command)), check=True, env=environment)

    def chroot(*command):
        run("chroot", root, *command)

    try:
        for source in ("/dev", "/proc", "/sys"):
            destination = root / source.lstrip("/")
            destination.mkdir(exist_ok=True)
            run("mount", "--bind", source, destination)
            mounted.append(destination)
        chroot("apt-get", "update")
        chroot("apt-get", "install", "-y", "--no-install-recommends", *PACKAGES)
        write(root, "etc/locale.gen", "en_GB.UTF-8 UTF-8\n")
        chroot("locale-gen")
        write(root, "etc/default/locale", "LANG=en_GB.UTF-8\n")
        write(root, "etc/gdm3/daemon.conf", (
            f"[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin={USERNAME}\n"
            "[security]\n[xdmcp]\n[chooser]\n[debug]\n"
        ))
        (root / "etc/systemd/system/default.target").unlink()
        (root / "etc/systemd/system/default.target").symlink_to("/usr/lib/systemd/system/graphical.target")
        chroot("systemctl", "enable", "gdm3.service", "NetworkManager.service", "bluetooth.service")
        write(root, "etc/NetworkManager/conf.d/10-debport-usb.conf", (
            "[keyfile]\nunmanaged-devices=interface-name:usb0;interface-name:rndis0\n"
        ))
        write(root, "etc/motd", "Debian GNOME SM-T505 preview. Downstream hardware adaptation in progress.\n")
        write(root, "etc/issue", f"Debian 13 GNOME SM-T505 - USB SSH: {USERNAME}@172.16.42.1\n")
        chroot("apt-get", "clean")
        chroot("dpkg", "--audit")
        with (output / "packages.tsv").open("w") as stream:
            subprocess.run(["chroot", str(root), "dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"],
                           stdout=stream, check=True)
        manifest["stage"] = "userspace-ready-device-adaptation-pending"
    except BaseException as error:
        manifest.update(stage="failed", error=str(error))
        raise
    finally:
        for destination in reversed(mounted):
            subprocess.run(["umount", str(destination)], check=True)
        receipt.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
