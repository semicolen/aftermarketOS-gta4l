"""Capture native GNOME boot evidence without logging the local sudo password."""
import argparse
import json
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=repo / "out/debian-gnome-r1/runtime-fix/boot-evidence.json")
parser.add_argument("--credentials", type=Path, default=repo / ".cache/keys/debport-gnome-login.json")
args = parser.parse_args()
login = json.loads(args.credentials.read_text())
destination = login.get("username", "debian") + "@172.16.42.1"
keys = repo / ".cache/keys"
options = ["-i", ".cache/keys/debport-test", "-o", "IdentitiesOnly=yes",
           "-o", "UserKnownHostsFile=.cache/keys/debport-gnome-known-hosts",
           "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
subprocess.run(["scp", *options, "tools/inspect-gnome-boot.py",
                destination + ":/tmp/inspect-gnome-boot.py"], check=True, cwd=repo)
password = login["password"]
result = subprocess.run(["ssh", *options, destination,
                         "sudo -S -p '' python3 /tmp/inspect-gnome-boot.py"],
                        input=password + "\n", text=True, capture_output=True, timeout=180, check=True, cwd=repo)
evidence = json.loads(result.stdout)
output = args.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps({"evidence": str(output), "system_state": evidence["system_state"],
                  "gnome_processes": evidence["gnome_processes"], "failed_units": evidence["failed_units"]}, indent=2))
