"""Read-only boot evidence, run as root on the SM-T505 after GNOME startup."""
import json
import os
from pathlib import Path
import pwd
import subprocess


def command(*args):
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=12)
        return {"status": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}


units = ["gdm3.service", "NetworkManager.service", "bluetooth.service", "ModemManager.service",
         "iio-sensor-proxy.service", "debport-usb-network.service", "ssh.service"]
units += ["gta4l-" + name + ".service" for name in (
    "qrtr", "pd-mapper", "tqftpserv", "rmtfs", "adsp", "modem", "ipa", "wlan",
    "bluetooth", "sensors", "camera", "gps-assistance")]
evidence = {"os_release": Path("/etc/os-release").read_text(), "kernel": command("uname", "-a"),
            "system_state": command("systemctl", "is-system-running"),
            "failed_units": command("systemctl", "--failed", "--no-pager", "--plain"),
            "units": {name: command("systemctl", "show", name, "-p", "ActiveState", "-p", "SubState", "-p", "Result", "-p", "ExecMainStatus") for name in units},
            "network": command("nmcli", "device", "status"),
            "bluetooth": command("bluetoothctl", "show"),
            "modems": command("mmcli", "-L"),
            "sensors": command("gdbus", "call", "--system", "--dest", "net.hadess.SensorProxy",
                "--object-path", "/net/hadess/SensorProxy", "--method", "org.freedesktop.DBus.Properties.GetAll", "net.hadess.SensorProxy"),
            "audio_cards": Path("/proc/asound/cards").read_text() if Path("/proc/asound/cards").exists() else None,
            "gnome_processes": []}
identity = json.loads(Path("/etc/debport-image.json").read_text())
uid = pwd.getpwnam(identity.get("username", "debian")).pw_uid
for directory in Path("/proc").iterdir():
    if not directory.name.isdigit():
        continue
    try:
        if directory.stat().st_uid != uid or (directory / "comm").read_text().strip() != "gnome-shell":
            continue
        maps = (directory / "maps").read_text().splitlines()
        private_maps = sorted({line.split()[-1] for line in maps if "/usr/lib/gta4l-" in line})
        gpu = []
        for fd in (directory / "fd").iterdir():
            try:
                target = os.readlink(fd)
                if "kgsl" in target or "/dev/dri/" in target:
                    gpu.append(target)
            except OSError:
                pass
        evidence["gnome_processes"].append({"pid": int(directory.name), "private_graphics_libraries": private_maps,
                                            "gpu_device_files": sorted(set(gpu))})
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
evidence["failed_service_logs"] = {}
for name, result in evidence["units"].items():
    if "ActiveState=failed" in result.get("stdout", ""):
        evidence["failed_service_logs"][name] = command("journalctl", "-b", "-u", name, "-n", "35", "--no-pager")
print(json.dumps(evidence, indent=2))
