#!/usr/bin/python3
"""Require working read-only RMTFS and contain modem SSR during bring-up."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--rmtfs-unit", choices=("gta4l-rmtfs.service", "gta4l-rmtfs-preflight.service"), default="gta4l-rmtfs.service")
args = parser.parse_args()
unit = args.rmtfs_unit
pid = subprocess.check_output(["systemctl", "show", unit, "--value", "-p", "MainPID"], text=True).strip()
if not pid.isdecimal() or int(pid) == 0:
    raise ValueError("read-only RMTFS must be running before the modem")
subprocess.run(["/usr/libexec/gta4l-rmtfs-ready", "--wait", pid], check=True)
matches = [path for path in Path("/sys/bus/msm_subsys/devices").iterdir()
           if (path / "name").read_text().strip() == "modem"]
if len(matches) != 1:
    raise ValueError("modem subsystem mapping is ambiguous")
modem = matches[0]
level = modem / "restart_level"
if level.read_text().strip() not in ("SYSTEM", "RELATED"):
    raise ValueError("unexpected subsystem restart policy")
Path("/run/debport-modem-restart-before").write_text(level.read_text())
level.write_text("RELATED\n")
if level.read_text().strip() != "RELATED":
    raise ValueError("modem-only recovery policy was not applied")
print("MODEM_PREFLIGHT_READ_ONLY_RMTFS_AND_RELATED_SSR_OK")
