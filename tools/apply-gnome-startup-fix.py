"""Apply the recorded first-boot service corrections to a GNOME preview tree."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, required=True)
    args = parser.parse_args()
    root = args.rootfs.resolve()
    identity = json.loads((root / "etc/debport-image.json").read_text())
    if identity.get("device") != "samsung-gta4l" or identity.get("desktop") != "gnome":
        raise ValueError("expected the SM-T505 GNOME image")
    if (root / "etc/debport/enable-modem").exists():
        raise ValueError("modem opt-in already exists; refusing an ambiguous boot test")
    changes = {}
    for name in ("gta4l-modem", "gta4l-rmtfs", "gta4l-ipa", "gta4l-wlan",
                 "ModemManager", "gta4l-gps-assistance"):
        changes["etc/systemd/system/" + name + ".service.d/20-modem-preview.conf"] = (
            "[Unit]\nConditionPathExists=/etc/debport/enable-modem\n")
    changes["etc/systemd/system/NetworkManager.service.d/10-gta4l.conf"] = (
        "[Unit]\nWants=gta4l-wlan.service\n")
    relative = "etc/systemd/system/gta4l-qrtr.service"
    text = (root / relative).read_text()
    original = "ExecStart=/usr/lib/debport-device/bin/qrtr-ns\n"
    corrected = "ExecStart=/usr/lib/debport-device/bin/qrtr-ns -f\n"
    if original not in text and corrected not in text:
        raise ValueError("unexpected QRTR service command")
    changes[relative] = text.replace(original, corrected)
    relative = "usr/bin/gta4l-bt-initialize"
    text = (root / relative).read_text()
    if "/usr/sbin/btattach" not in text and "/usr/bin/btattach" not in text:
        raise ValueError("unexpected Bluetooth initializer")
    if not (root / "usr/bin/btattach").is_file():
        raise ValueError("Debian btattach is missing")
    changes[relative] = text.replace("/usr/sbin/btattach", "/usr/bin/btattach")
    backup = root / "var/lib/debport/gnome-startup-r2-before.tar"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.parent.chmod(0o700)
    if not backup.exists():
        with tarfile.open(backup, "x") as archive:
            for relative in changes:
                if (root / relative).exists():
                    archive.add(root / relative, arcname=relative, recursive=False)
    backup.chmod(0o600)
    receipt = {"revision": "gnome-startup-r2", "modem_enabled": False, "changes": {}}
    for relative, text in changes.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o755)
        path.write_text(text)
        path.chmod(0o755 if relative == "usr/bin/gta4l-bt-initialize" else 0o644)
        receipt["changes"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    destination = root / "usr/share/debport/gnome-startup-r2.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.parent.chmod(0o755)
    destination.write_text(json.dumps(receipt, indent=2) + "\n")
    destination.chmod(0o644)
    # NetworkManager owns desktop connectivity; USB DHCP is an explicit service.
    # The base system's empty networkd setup must not delay network-online.
    wait = root / "etc/systemd/system/systemd-networkd-wait-online.service"
    if wait.is_symlink() and str(wait.readlink()) == "/dev/null":
        pass
    elif wait.exists() or wait.is_symlink():
        raise ValueError("unexpected networkd wait-online override")
    else:
        wait.symlink_to("/dev/null")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
