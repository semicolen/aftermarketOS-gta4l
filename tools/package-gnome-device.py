"""Package a guarded GNOME upgrade using recovery-compatible rootfs chunks."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))
from debport.android_boot import BootImage, replace_initramfs

CHUNK_BYTES = 768 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def add(archive, name, data, executable=False):
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--boot-before", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", type=int, default=2)
    parser.add_argument("--headless-manifest", type=Path,
                        help="manifest for the verified predecessor; otherwise use the historical local path")
    parser.add_argument("--recovery-runtime", type=Path,
                        help="recovery e2fsck runtime tar.gz; otherwise read the historical predecessor ZIP")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    previous_path = args.headless_manifest or repo / "out/debian-device-test-r4/manifest.json"
    previous = json.loads(previous_path.read_text())
    before = args.boot_before.read_bytes()
    if len(before) != 100663296 or sha(before) != previous["expected_full_boot_after_sha256"]:
        raise ValueError("successful headless boot backup mismatch")
    rootfs_manifest = json.loads((args.rootfs.parent / "rootfs-manifest.json").read_text())
    rootfs_sha = sha_file(args.rootfs)
    rootfs_bytes = args.rootfs.stat().st_size
    if rootfs_sha != rootfs_manifest["image_sha256"] or rootfs_manifest["identity"]["desktop"] != "gnome":
        raise ValueError("GNOME filesystem manifest mismatch")
    if rootfs_bytes != 6 * 1024 * 1024 * 1024:
        raise ValueError("expected a 6 GiB GNOME image")
    args.output.mkdir(exist_ok=False)
    image = BootImage.parse(before)
    stage_two = (repo / "boot/samsung-gta4l-init-2nd.sh").read_bytes().replace(
        b"debian-test-20261018.ext4", b"gnome-20261018.ext4")
    ramdisk = replace_initramfs(image.ramdisk, {"init_2nd.sh": (stage_two, 0o100755)})
    cmdline = " ".join(item for item in image.cmdline.split() if not item.startswith((
        "systemd.unit=", "loglevel=", "systemd.show_status=")))
    cmdline += " systemd.unit=graphical.target loglevel=3 systemd.show_status=auto"
    boot = image.pack(ramdisk=ramdisk, cmdline=cmdline)
    parsed = BootImage.parse(boot)
    if parsed.kernel != image.kernel or parsed.dtb != image.dtb:
        raise ValueError("kernel or DTB changed")
    if args.recovery_runtime:
        runtime = args.recovery_runtime.read_bytes()
        if sha(runtime) != previous["recovery_runtime_sha256"]:
            raise ValueError("recovery runtime checksum mismatch")
    else:
        with zipfile.ZipFile(previous_path.parent / previous["installer"]) as archive:
            runtime = archive.read("recovery-runtime.tar.gz")
    entries = [f"rootfs/{number:03}.ext4" for number in range((rootfs_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES)]
    values = {
        "OLD_BOOT_SHA": sha(before), "ORIGINAL_BOOT_SHA": previous["original_full_boot_sha256"],
        "RECOVERY_SHA": previous["recovery_sha256"], "MBR_SHA": previous["userdata_mbr_sha256"],
        "NEW_BOOT_BYTES": str(len(boot)), "NEW_BOOT_SHA": sha(boot),
        "NEW_FULL_BOOT_SHA": sha(boot + before[len(boot):]), "ROOTFS_SHA": rootfs_sha,
        "ROOTFS_BYTES": str(rootfs_bytes), "NEEDED_KIB": str(rootfs_bytes // 1024 + 524288),
        "FSCK_RUNTIME_SHA": sha(runtime), "ROOTFS_ENTRIES": " ".join(entries),
    }
    scripts = {}
    for name, template in (("install", "install-gnome.sh"), ("rollback", "rollback-debian-test.sh")):
        text = (repo / "recovery" / template).read_text()
        for key, value in values.items():
            text = text.replace("@" + key + "@", value)
        if "@" in text.replace("debian@172.16.42.1", ""):
            raise ValueError("unexpanded installer placeholder")
        path = args.output / (name + ".sh")
        path.write_text(text, newline="\n")
        subprocess.run(["sh", "-n", str(path)], check=True)
        scripts[name] = text.encode()
    (args.output / "boot.img").write_bytes(boot)
    installer = args.output / f"Debian-SM-T505-OrangeFox-GNOME-r{args.revision}.zip"
    rollback = args.output / "SM-T505-restore-working-headless-Debian.zip"
    chunks = []
    with zipfile.ZipFile(installer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=False) as archive:
        add(archive, "META-INF/com/google/android/update-binary", scripts["install"], executable=True)
        add(archive, "META-INF/com/google/android/updater-script", b"# Guarded Debian GNOME upgrade\n")
        add(archive, "boot.img", boot)
        add(archive, "recovery-runtime.tar.gz", runtime)
        with args.rootfs.open("rb") as stream:
            for entry in entries:
                length = min(CHUNK_BYTES, rootfs_bytes - stream.tell())
                info = zipfile.ZipInfo(entry)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                info.file_size = length
                checksum = hashlib.sha256()
                remaining = length
                with archive.open(info, "w", force_zip64=False) as target:
                    while remaining:
                        data = stream.read(min(1024 * 1024, remaining))
                        if not data:
                            raise ValueError("truncated GNOME filesystem")
                        checksum.update(data)
                        target.write(data)
                        remaining -= len(data)
                chunks.append({"entry": entry, "bytes": length, "sha256": checksum.hexdigest()})
    with zipfile.ZipFile(rollback, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        add(archive, "META-INF/com/google/android/update-binary", scripts["rollback"], executable=True)
        add(archive, "META-INF/com/google/android/updater-script", b"# Restore successful headless Debian boot\n")
        add(archive, "boot-before.img", before)
    for path in (installer, rollback):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("archive CRC verification failed")
    receipt = {"device": "SM-T505", "desktop": "gnome", "device_boot_tested": False,
               "kernel_unchanged": True, "dtb_unchanged": True, "rootfs": rootfs_manifest,
               "boot_sha256": sha(boot), "expected_full_boot_after_sha256": values["NEW_FULL_BOOT_SHA"],
               "previous_full_boot_sha256": sha(before), "recovery_sha256": values["RECOVERY_SHA"],
               "userdata_mbr_sha256": values["MBR_SHA"], "rootfs_chunks": chunks,
               "installer": installer.name, "installer_bytes": installer.stat().st_size,
               "installer_sha256": sha_file(installer), "rollback": rollback.name,
               "rollback_sha256": sha_file(rollback), "preserves_headless_image": True,
               "formats_or_repartitions": False}
    (args.output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
