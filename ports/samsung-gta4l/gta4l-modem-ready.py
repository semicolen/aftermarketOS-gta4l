#!/usr/bin/python3
"""Wait until downstream MPSS is online and exports its QMI control service."""
from pathlib import Path
import subprocess
import time

matches = [path for path in Path("/sys/bus/msm_subsys/devices").iterdir()
           if (path / "name").read_text().strip() == "modem"]
if len(matches) != 1:
    raise ValueError("modem subsystem mapping is ambiguous")
modem = matches[0]
for attempt in range(15):
    if int((modem / "crash_count").read_text()) != 0:
        raise RuntimeError("modem crashed during startup")
    result = subprocess.run(["/usr/lib/debport-device/bin/qrtr-lookup"],
                            text=True, capture_output=True, timeout=3)
    dms = any(line.split()[:4] == ["2", "1", "0", "0"] for line in result.stdout.splitlines())
    if (modem / "state").read_text().strip() == "ONLINE" and dms:
        print("MODEM_ONLINE_QMI_READY")
        break
    time.sleep(0.5)
else:
    raise RuntimeError("modem did not become ready")
