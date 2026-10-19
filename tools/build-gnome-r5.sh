#!/bin/sh
# Build postmarketOS-compatible local login defaults on the verified r4 userspace.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=/var/tmp/debport-gta4l-gnome-20261019-r6
compiler=/var/tmp/debport-gnome-builder-r1
compat=bubblewrap_0.12.0-1~deb13u1+debport1_arm64.deb
test ! -e "$work"
test -f "$compiler/build/receipts/bubblewrap.json"
mkdir "$work"
cp -a /var/tmp/debport-gta4l-gnome-20261019-r5/rootfs "$work/rootfs"
cp /var/tmp/debport-gta4l-gnome-20261019-r5/userspace-manifest.json "$work/userspace-manifest.json"
cp "$compiler/build/debian-sources/$compat" "$work/$compat"
root=$work/rootfs
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
python3 "$repo/tools/integrate-gta4l-gnome.py" --rootfs "$root" \
    --compiler "$compiler" \
    --runtime "$repo/out/recovery-backup-20261018/desktop-runtime.tar" > "$work/integrate.log" 2>&1
python3 "$repo/tools/finalize-gnome-image.py" --work "$work" > "$work/finalize.log" 2>&1
python3 "$repo/tools/package-gnome-device.py" --rootfs "$work/rootfs.ext4" \
    --boot-before "$repo/out/recovery-backup-20261018/boot-debian-headless-r4.img" \
    --output "$repo/out/debian-gnome-r5" --revision 5 > "$work/package.log" 2>&1
cp "$work/debport-gta4l-gnome_0.1.4_arm64.deb" "$work/rootfs-manifest.json" \
   "$work/packages-final.tsv" "$work/userspace-manifest.json" "$work/$compat" \
   "$work/login-defaults.json" "$work/login-verification.json" "$repo/out/debian-gnome-r5/"
cp "$compiler/build/receipts/bubblewrap.json" "$repo/out/debian-gnome-r5/"
echo GNOME_R5_BUILD_COMPLETE
