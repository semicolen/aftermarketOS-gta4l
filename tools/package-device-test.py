"""Build a guarded SM-T505 Debian boot-test ZIP and its exact boot rollback."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))
from debport.android_boot import BootImage, read_newc, replace_initramfs


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def add_bytes(archive, name, data, executable=False):
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", type=int, default=1)
    args = parser.parse_args()
    if args.revision < 1 or args.rootfs.stat().st_size != 1610612736:
        raise ValueError("expected a positive revision and 1.5 GiB recovery-compatible filesystem")
    source = Path(__file__).resolve().parents[1]
    backup = json.loads((args.backup / "manifest.json").read_text())
    before = (args.backup / "boot.img").read_bytes()
    if len(before) != 100663296 or sha(before) != backup["partitions"]["boot"]["sha256"]:
        raise ValueError("boot backup checksum mismatch")
    image = BootImage.parse(before)
    kernel = gzip.decompress(image.kernel)
    if kernel[0x38:0x3c] != b"ARM\x64" or b"#11-postmarketOS" not in kernel:
        raise ValueError("unexpected device kernel")
    args.output.mkdir(parents=True, exist_ok=False)
    stage_two = (source / "boot/samsung-gta4l-init-2nd.sh").read_bytes()
    ramdisk = replace_initramfs(image.ramdisk, {"init_2nd.sh": (stage_two, 0o100755)})
    args_to_keep = [item for item in image.cmdline.split() if item not in ("pmos.debug-shell", "pmos_debug_shell", "console=tty0") and not item.startswith("panic=")]
    cmdline = " ".join(args_to_keep + ["console=tty0", "pmos.nosplash", "systemd.unit=multi-user.target", "systemd.log_target=kmsg", "systemd.show_status=1", "net.ifnames=0", "panic=0"])
    boot = image.pack(ramdisk=ramdisk, cmdline=cmdline)
    parsed = BootImage.parse(boot)
    if parsed.kernel != image.kernel or parsed.dtb != image.dtb:
        raise ValueError("kernel/DTB changed unexpectedly")
    original_records = list(read_newc(gzip.decompress(image.ramdisk)))
    original_entries = {name: data for name, data, _, _ in original_records}
    new_entries = {name: data for name, data, _, _ in read_newc(gzip.decompress(parsed.ramdisk))}
    for name, data in original_entries.items():
        if name != "init_2nd.sh" and new_entries.get(name) != data:
            raise ValueError(f"unexpected initramfs change: {name}")
    full_after_sha = sha(boot + before[len(boot):])
    rootfs_manifest = json.loads((args.rootfs.parent / "rootfs-manifest.json").read_text())
    rootfs_sha = sha_file(args.rootfs)
    if rootfs_sha != rootfs_manifest["image_sha256"]:
        raise ValueError("rootfs manifest checksum mismatch")
    runtime_data = io.BytesIO()
    selected = [(name, data, fields) for name, data, fields, _ in original_records
                if name == "usr/bin/e2fsck" or (name.startswith("usr/lib/") and name.count("/") == 2
                and (fields[1] & 0o170000) in (0o100000, 0o120000))]
    selected_basenames = {Path(name).name for name, _, _ in selected}
    with tarfile.open(fileobj=runtime_data, mode="w:gz") as archive:
        for directory in ("usr", "usr/bin", "usr/lib"):
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            archive.addfile(info)
        for name, data, fields in selected:
            info = tarfile.TarInfo(name)
            info.mode = fields[1] & 0o777
            if fields[1] & 0o170000 == 0o120000:
                info.type = tarfile.SYMTYPE
                info.linkname = Path(data.decode()).name
                if info.linkname not in selected_basenames:
                    raise ValueError("filesystem-checker runtime has an external symlink")
                archive.addfile(info)
            else:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    runtime = runtime_data.getvalue()
    values = {
        "OLD_BOOT_SHA": sha(before), "RECOVERY_SHA": backup["partitions"]["recovery"]["sha256"],
        "MBR_SHA": sha((args.backup / "userdata-mbr.bin").read_bytes()),
        "NEW_BOOT_BYTES": str(len(boot)), "NEW_BOOT_SHA": sha(boot),
        "NEW_FULL_BOOT_SHA": full_after_sha, "ROOTFS_SHA": rootfs_sha,
        "FSCK_RUNTIME_SHA": sha(runtime)
    }
    scripts = {}
    for stem in ("install", "rollback"):
        script = (source / f"recovery/{stem}-debian-test.sh").read_text()
        for key, value in values.items():
            script = script.replace("@" + key + "@", value)
        if "@" in script.replace("debian@172.16.42.1", ""):
            raise ValueError("unexpanded installer placeholder")
        target = args.output / f"{stem}.sh"
        target.write_text(script, newline="\n")
        subprocess.run(["sh", "-n", str(target)], check=True)
        scripts[stem] = script.encode()
    (args.output / "boot.img").write_bytes(boot)
    installer = args.output / f"Debian-SM-T505-OrangeFox-boot-test-r{args.revision}.zip"
    rollback = args.output / "SM-T505-restore-previous-boot.zip"
    for path, script in ((installer, scripts["install"]), (rollback, scripts["rollback"])):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            add_bytes(archive, "META-INF/com/google/android/update-binary", script, executable=True)
            add_bytes(archive, "META-INF/com/google/android/updater-script", b"# Guarded SM-T505 boot test\n")
            if path == installer:
                add_bytes(archive, "boot.img", boot)
                add_bytes(archive, "recovery-runtime.tar.gz", runtime)
                archive.write(args.rootfs, "rootfs.ext4")
            else:
                add_bytes(archive, "boot-before.img", before)
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC check failed")
    manifest = {
        "type": "headless-device-boot-test", "device": "SM-T505", "device_boot_tested": False,
        "revision": args.revision,
        "kernel_unchanged": True, "dtb_unchanged": True, "early_firmware_unchanged": True,
        "modified_initramfs_files": ["init_2nd.sh"], "rootfs": rootfs_manifest,
        "boot_sha256": sha(boot), "boot_bytes": len(boot), "expected_full_boot_after_sha256": full_after_sha,
        "original_full_boot_sha256": sha(before), "recovery_sha256": values["RECOVERY_SHA"],
        "userdata_mbr_sha256": values["MBR_SHA"], "partition_writes": ["boot"],
        "filesystem_additions": ["/var/lib/debport/debian-test-20261018.ext4", "/var/lib/debport/boot-before-debian.img"],
        "formats_userdata": False, "graphical_desktop": False, "ssh": "debian@172.16.42.1 with dedicated host key",
        "installer": installer.name, "installer_sha256": sha_file(installer),
        "rollback": rollback.name, "rollback_sha256": sha_file(rollback)
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
