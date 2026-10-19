"""Run a command on the local GNOME preview, keeping sudo credentials off argv."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--sudo", action="store_true")
parser.add_argument("--output", type=Path)
parser.add_argument("--binary", action="store_true")
parser.add_argument("--credentials", type=Path, help="login JSON for the selected image")
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()
if args.command[:1] == ["--"]:
    args.command.pop(0)
if not args.command:
    parser.error("a command is required")
if args.binary and not args.output:
    parser.error("binary capture requires --output")
repo = Path(__file__).resolve().parents[1]
login_path = args.credentials or repo / ".cache/keys/debport-gnome-login.json"
login = json.loads(login_path.read_text())
username = login.get("username", "debian")
options = ["-i", ".cache/keys/debport-test", "-o", "IdentitiesOnly=yes",
           "-o", "UserKnownHostsFile=.cache/keys/debport-gnome-known-hosts",
           "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
command = shlex.join(args.command)
password = None
if args.sudo:
    command = "sudo -S -p '' -- " + command
    password = login["password"] + "\n"
result = subprocess.run(["ssh", *options, username + "@172.16.42.1", command],
                        input=password.encode() if args.binary and password else password,
                        text=not args.binary, encoding=None if args.binary else "utf-8",
                        errors=None if args.binary else "replace", capture_output=True, cwd=repo, timeout=180)
if args.output:
    if args.binary:
        args.output.write_bytes(result.stdout)
    else:
        args.output.write_text(result.stdout, encoding="utf-8")
else:
    print(result.stdout, end="")
if result.stderr:
    print(result.stderr.decode(errors="replace") if args.binary else result.stderr, end="")
raise SystemExit(result.returncode)
