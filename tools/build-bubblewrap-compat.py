"""Build Debian's current bubblewrap with its upstream Linux 4.19 fallback."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


VERSION = "0.12.0-1~deb13u1+debport1"
DSC_SHA256 = "1abef77e6c35ce6c48c8969d31bffcc7a589bfd8e8fea9284fd8d77750f01d39"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder", type=Path, required=True)
    args = parser.parse_args()
    root = args.builder.resolve()
    sources = root / "build/debian-sources"
    dsc = sources / "bubblewrap_0.12.0-1~deb13u1.dsc"
    if hashlib.sha256(dsc.read_bytes()).hexdigest() != DSC_SHA256:
        raise ValueError("unexpected Debian source descriptor")
    source = sources / "bubblewrap-0.12.0"
    rules = source / "debian/rules"
    text = rules.read_text()
    if "-Dassume_kernel=5.10.0" not in text and "-Dassume_kernel=4.19.0" not in text:
        raise ValueError("unexpected bubblewrap build configuration")
    rules.write_text(text.replace("-Dassume_kernel=5.10.0", "-Dassume_kernel=4.19.0"))
    changelog = source / "debian/changelog"
    text = changelog.read_text()
    if not text.startswith(f"bubblewrap ({VERSION})"):
        changelog.write_text(
            f"bubblewrap ({VERSION}) trixie; urgency=medium\n\n"
            "  * Enable upstream's openat2 fallback for downstream Linux 4.19.\n"
            "    Retain namespace isolation and the 0.12.0 security fixes.\n\n"
            " -- debport local build <debport@localhost>  Mon, 19 Oct 2026 17:10:00 +0000\n\n"
            + text
        )
    subprocess.run([
        "chroot", str(root), "/usr/bin/env", "-C", "/build/debian-sources/bubblewrap-0.12.0",
        "DEB_BUILD_OPTIONS=nocheck", "dpkg-buildpackage", "--build=binary", "--host-arch=arm64",
        "--build-profiles=nocheck", "--no-sign", "-j4",
    ], check=True)
    package = sources / f"bubblewrap_{VERSION}_arm64.deb"
    receipt = {
        "component": "bubblewrap", "status": "built", "version": VERSION,
        "source_dsc_sha256": DSC_SHA256, "assume_kernel": "4.19.0",
        "package": str(package.relative_to(root)),
        "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "cross_build_tests": "not run; native device sandbox smoke test required",
    }
    (root / "build/receipts/bubblewrap.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
