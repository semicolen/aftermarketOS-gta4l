#!/bin/sh
# Preserve the first preview and assemble its corrected successor.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=/var/tmp/debport-gta4l-gnome-20261018-r3
test ! -e "$work"
mkdir "$work"
cp -a /var/tmp/debport-gta4l-gnome-20261018-r2/rootfs "$work/rootfs"
cp /var/tmp/debport-gta4l-gnome-20261018-r2/userspace-manifest.json "$work/userspace-manifest.json"
python3 "$repo/tools/integrate-gta4l-gnome.py" --rootfs "$work/rootfs" \
    --compiler /var/tmp/debport-gnome-builder-r1 \
    --runtime "$repo/out/recovery-backup-20261018/desktop-runtime.tar" > "$work/integrate.log" 2>&1
python3 "$repo/tools/finalize-gnome-image.py" --work "$work" \
    --credentials "$repo/.cache/keys/debport-gnome-login.json" > "$work/finalize.log" 2>&1
python3 "$repo/tools/package-gnome-device.py" --rootfs "$work/rootfs.ext4" \
    --boot-before "$repo/out/recovery-backup-20261018/boot-debian-headless-r4.img" \
    --output "$repo/out/debian-gnome-r2" --revision 2 > "$work/package.log" 2>&1
cp "$work/debport-gta4l-gnome_0.1.1_arm64.deb" "$work/rootfs-manifest.json" \
   "$work/packages-final.tsv" "$work/userspace-manifest.json" "$repo/out/debian-gnome-r2/"
echo GNOME_R2_BUILD_COMPLETE
