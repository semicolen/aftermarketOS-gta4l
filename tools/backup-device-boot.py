"""Read and verify SM-T505 boot/recovery backups. Never writes tablet partitions."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="verify existing complete backups instead of overwriting")
    args = parser.parse_args()
    adb = ["adb", "-s", args.serial]

    def query(*command):
        return subprocess.check_output(adb + ["shell", *command], text=True).strip()

    device = query("getprop", "ro.product.device")
    model = query("getprop", "ro.product.model")
    if query("id", "-u") != "0" or device != "gta4l" or model not in ("SM-T505", "SM_T505"):
        raise ValueError("expected root OrangeFox recovery on SM-T505")
    args.output.mkdir(parents=True, exist_ok=args.resume)
    report = {"serial": args.serial, "model": model, "device": device,
              "bootloader": query("getprop", "ro.bootloader"), "partitions": {}}
    for name in ("boot", "recovery"):
        node = "/dev/block/by-name/" + name
        size = int(query("blockdev", "--getsize64", node))
        if not 0 < size <= 128 * 1024 * 1024:
            raise ValueError("unexpected partition size")
        target = args.output / f"{name}.img"
        if not (args.resume and target.is_file()):
            with target.open("xb") as stream:
                subprocess.run(adb + ["exec-out", "cat", node], stdout=stream, check=True)
        with target.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        remote = query("sha256sum", node).split()[0]
        if target.stat().st_size != size or digest != remote:
            raise ValueError(f"incomplete or inconsistent {name} backup")
        report["partitions"][name] = {"bytes": size, "sha256": digest, "remote_sha256": remote}
        (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Verified {name} backup ({size} bytes)", flush=True)
    mbr = subprocess.check_output(adb + ["exec-out", "dd if=/dev/block/by-name/userdata bs=512 count=1 2>/dev/null"])
    if len(mbr) != 512:
        raise ValueError("short userdata MBR read")
    (args.output / "userdata-mbr.bin").write_bytes(mbr)
    report["userdata_mbr_valid"] = mbr[510:512] == b"\x55\xaa"
    report["userdata_partitions"] = []
    for n in range(4):
        entry = mbr[446 + n * 16:462 + n * 16]
        start, sectors = struct.unpack_from("<II", entry, 8)
        if entry[4]:
            report["userdata_partitions"].append({"index": n + 1, "type": entry[4],
                                                   "start_sector": start, "sectors": sectors})
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
