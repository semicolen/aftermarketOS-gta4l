"""Stream only the four RMTFS storage partitions to a private backup tar."""
import fcntl
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tarfile

identity = json.loads(Path("/etc/debport-image.json").read_text())
if os.geteuid() != 0 or identity["device"] != "samsung-gta4l":
    raise ValueError("SM-T505 root required")
partitions = {"modemst1": 61, "modemst2": 62, "fsg": 59, "fsc": 60}
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
    for name, number in partitions.items():
        path = Path("/dev/disk/by-partlabel") / name
        if path.resolve() != Path("/dev/mmcblk0p" + str(number)) or not stat.S_ISBLK(path.stat().st_mode):
            raise ValueError("partition mapping changed: " + name)
        with path.open("rb", buffering=0) as stream:
            size = struct.unpack("Q", fcntl.ioctl(stream, 0x80081272, bytes(8)))[0]
            if not 0 < size <= 16 * 1024 * 1024:
                raise ValueError("unexpected modem storage size")
            info = tarfile.TarInfo(name + ".img")
            info.size = size
            info.mode = 0o600
            archive.addfile(info, stream)
