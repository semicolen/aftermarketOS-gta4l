#!/usr/bin/python3
"""Require the correct UIO mapping, NV labels, and live RMTFS QRTR server."""
import argparse
import os
from pathlib import Path
import stat
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--wait", type=int)
args = parser.parse_args()
alias = Path("/dev/qcom_rmtfs_uio1")
device = alias.resolve(strict=True)
if device.parent != Path("/dev") or not device.name.startswith("uio") or not stat.S_ISCHR(device.stat().st_mode):
    raise ValueError("invalid RMTFS UIO device")
sysfs = Path("/sys/class/uio") / device.name
if (sysfs / "name").read_text().strip() != "rmtfs":
    raise ValueError("UIO device is not modem storage")
if int((sysfs / "maps/map0/size").read_text(), 16) != 0x200000:
    raise ValueError("RMTFS shared memory geometry changed")
for name, number in {"modemst1": 61, "modemst2": 62, "fsg": 59, "fsc": 60}.items():
    path = Path("/dev/disk/by-partlabel") / name
    if path.resolve() != Path("/dev/mmcblk0p" + str(number)) or not stat.S_ISBLK(path.stat().st_mode):
        raise ValueError("RMTFS partition mapping changed: " + name)
if args.wait:
    process = Path("/proc") / str(args.wait)
    command = (process / "cmdline").read_bytes().split(b"\0")
    if command[:3] != [b"/usr/bin/rmtfs", b"-P", b"-r"] or b"-s" in command:
        raise ValueError("RMTFS must use read-only storage without remoteproc startup")
    for attempt in range(20):
        mapped = str(device) in (process / "maps").read_text()
        result = subprocess.run(["/usr/lib/debport-device/bin/qrtr-lookup"],
                                text=True, capture_output=True, timeout=4)
        ready = any(line.split()[:5] == ["14", "1", "0", "1", "14"] for line in result.stdout.splitlines())
        if mapped and ready:
            print("RMTFS_READY_READ_ONLY_UIO_AND_QRTR")
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("RMTFS did not map UIO and register QRTR service 14")
else:
    print("RMTFS_DEVICE_PREFLIGHT_OK")
