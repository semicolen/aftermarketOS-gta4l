"""Compare a rebuilt image's startup files with the tested device corrections."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--rootfs", type=Path, required=True)
parser.add_argument("--receipt", type=Path, required=True)
args = parser.parse_args()
receipt = json.loads(args.receipt.read_text())
for relative, expected in receipt["changes"].items():
    actual = hashlib.sha256((args.rootfs / relative).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError("rebuilt startup configuration differs: " + relative)
wait = args.rootfs / "etc/systemd/system/systemd-networkd-wait-online.service"
if not wait.is_symlink() or str(wait.readlink()) != "/dev/null":
    raise ValueError("unused networkd wait must be masked")
if (args.rootfs / "etc/debport/enable-modem").exists():
    raise ValueError("modem must remain off in the preview")
print(json.dumps({"tested_startup_files_match": len(receipt["changes"]),
                  "unused_networkd_wait": "masked", "modem_enabled": False}, indent=2))
