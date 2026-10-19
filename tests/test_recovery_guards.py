import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == "linux", "recovery shell guards run on Linux")
class RecoveryGuards(unittest.TestCase):
    def run_guard(self, mismatch, expected_message, template="install-debian-test.sh"):
        source = Path(__file__).resolve().parents[1] / "recovery" / template
        text = source.read_text()
        for key, value in {"OLD_BOOT_SHA": "a" * 64, "RECOVERY_SHA": "b" * 64,
                           "MBR_SHA": "c" * 64, "NEW_BOOT_SHA": "d" * 64,
                           "NEW_FULL_BOOT_SHA": "e" * 64, "ROOTFS_SHA": "f" * 64,
                           "FSCK_RUNTIME_SHA": "1" * 64, "NEW_BOOT_BYTES": "1234"}.items():
            text = text.replace("@" + key + "@", value)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            script = work / "installer.sh"
            script.write_text(text)
            mock = work / "command"
            mock.write_text("""#!/bin/sh
case "${0##*/}" in
id) echo 0 ;;
getprop)
  case "$1" in
  ro.product.device) if [ "$MISMATCH" = device ]; then echo wrong; else echo gta4l; fi ;;
  ro.bootloader) echo T505XXS8CXG1 ;;
  esac ;;
readlink)
  case "$2" in */boot) echo /dev/block/mmcblk0p69 ;; */userdata) echo /dev/block/mmcblk0p80 ;; esac ;;
blockdev)
  case "$2" in */mmcblk0p69) echo 100663296 ;; */mmcblk0p80) echo 23484415488 ;; esac ;;
sha256sum)
  case "$1" in
  /dev/block/mmcblk0p69) if [ "$MISMATCH" = boot ]; then printf '%064d  boot\\n' 0; else printf '%s  boot\\n' "$OLD_HASH"; fi ;;
  /dev/block/by-name/recovery) printf '%s  recovery\\n' "$RECOVERY_HASH" ;;
  *) cat >/dev/null; printf '%064d  table\\n' 0 ;;
  esac ;;
dd)
  for argument in "$@"; do case "$argument" in of=*) echo FORBIDDEN_WRITE >&2; exit 99 ;; esac; done
  printf mbr ;;
mountpoint) exit 1 ;;
*) echo UNEXPECTED_COMMAND >&2; exit 99 ;;
esac
""")
            mock.chmod(0o755)
            for command in ("id", "getprop", "readlink", "blockdev", "sha256sum", "dd", "mountpoint"):
                (work / command).symlink_to(mock)
            environment = {**os.environ, "PATH": f"{work}:{os.environ['PATH']}", "MISMATCH": mismatch,
                           "OLD_HASH": "a" * 64, "RECOVERY_HASH": "b" * 64}
            log = work / "ui.log"
            with log.open("w") as stream:
                result = subprocess.run(["sh", str(script), "3", str(stream.fileno()), "/missing.zip"],
                    env=environment, pass_fds=(stream.fileno(),), capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected_message, log.read_text())
            self.assertNotIn("FORBIDDEN_WRITE", result.stderr)
            self.assertNotIn("UNEXPECTED_COMMAND", result.stderr)

    def test_wrong_device_stops_before_any_write(self):
        self.run_guard("device", "wrong device")

    def test_changed_boot_stops_before_any_write(self):
        self.run_guard("boot", "current boot differs from backup")

    def test_changed_partition_table_stops_before_any_write(self):
        self.run_guard("mbr", "userdata table differs from backup")

    def test_gnome_wrong_device_stops_before_any_write(self):
        self.run_guard("device", "SM-T505 root recovery required", "install-gnome.sh")

    def test_gnome_changed_boot_stops_before_any_write(self):
        self.run_guard("boot", "current boot differs from successful Debian test", "install-gnome.sh")

    def test_gnome_changed_partition_table_stops_before_any_write(self):
        self.run_guard("mbr", "partition table changed", "install-gnome.sh")
