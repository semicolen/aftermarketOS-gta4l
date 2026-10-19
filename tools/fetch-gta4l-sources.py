"""Fetch pinned downstream sources, checking the port's published SHA512 values."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request

SOURCES = {
    "qrtr-ns-gta4l": ("qrtr-v1.2.tar.gz", "https://github.com/linux-msm/qrtr/archive/v1.2/qrtr-v1.2.tar.gz"),
    "pd-mapper-gta4l": ("pd-mapper-v1.1.tar.gz", "https://github.com/linux-msm/pd-mapper/archive/v1.1/pd-mapper-v1.1.tar.gz"),
    "tqftpserv-gta4l": ("tqftpserv-v1.2.tar.gz", "https://github.com/linux-msm/tqftpserv/archive/refs/tags/v1.2.tar.gz"),
    "hexagonrpc-gta4l": ("hexagonrpc-da7a3742ab8d5273a281b70ee11f16fb2cb6a690.tar.gz", "https://github.com/linux-msm/hexagonrpc/archive/da7a3742ab8d5273a281b70ee11f16fb2cb6a690.tar.gz"),
    "libssc": ("libssc-0.4.4.tar.gz", "https://codeberg.org/DylanVanAssche/libssc/archive/v0.4.4.tar.gz"),
    "iio-sensor-proxy": ("iio-sensor-proxy-3.9.tar.gz", "https://gitlab.freedesktop.org/hadess/iio-sensor-proxy/-/archive/3.9/iio-sensor-proxy-3.9.tar.gz"),
    "mesa-zink-kgsl-gta4l": ("mesa-26.0.8.tar.xz", "https://mesa.freedesktop.org/archive/mesa-26.0.8.tar.xz"),
    "mesa-vulkan-kgsl-gta4l": ("mesa-26.2.4.tar.xz", "https://mesa.freedesktop.org/archive/mesa-26.2.4.tar.xz"),
    "modemmanager": ("ModemManager-7f0bf17ab518cd78925cf7e53cc0d5c42f88b41a.tar.gz", "https://gitlab.freedesktop.org/mobile-broadband/ModemManager/-/archive/7f0bf17ab518cd78925cf7e53cc0d5c42f88b41a/ModemManager-7f0bf17ab518cd78925cf7e53cc0d5c42f88b41a.tar.gz"),
    "bubblewrap-gta4l": ("bubblewrap-0.13.0.tar.gz", "https://github.com/containers/bubblewrap/archive/v0.13.0.tar.gz"),
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha512").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1] / "upstream/2gta4l"
    args.output.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    receipts = []
    for package, (filename, url) in SOURCES.items():
        recipe = (repo / "port" / package / "APKBUILD").read_text()
        checksums = dict((name, value) for value, name in re.findall(r"^([a-f0-9]{128})\s+(\S+)\s*$", recipe, re.M))
        expected = checksums[filename]
        path = args.output / filename
        if not path.exists():
            pending = path.with_suffix(path.suffix + ".partial")
            print("Downloading", filename, flush=True)
            errors = []
            for candidate in (url, "https://distfiles.alpinelinux.org/distfiles/edge/" + filename):
                try:
                    with urllib.request.urlopen(candidate, timeout=60) as response, pending.open("wb") as stream:
                        while chunk := response.read(1024 * 1024):
                            stream.write(chunk)
                    if digest(pending) != expected:
                        raise ValueError("source checksum mismatch")
                    break
                except Exception as error:
                    errors.append(f"{candidate}: {error}")
            else:
                raise ValueError(f"No checksum-verified source for {filename}: {errors}")
            pending.rename(path)
        if digest(path) != expected:
            raise ValueError(f"cached source checksum mismatch: {filename}")
        receipts.append({"package": package, "file": filename, "url": url, "sha512": expected})
        (args.output / "sources.json").write_text(json.dumps({"port_revision": revision, "sources": receipts}, indent=2) + "\n")
        print("Verified", filename, flush=True)


if __name__ == "__main__":
    main()
