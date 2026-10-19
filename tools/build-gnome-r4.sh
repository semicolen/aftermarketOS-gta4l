#!/bin/sh
# Assemble the speaker, sandboxed gallery and compressed-memory corrections.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=/var/tmp/debport-gta4l-gnome-20261019-r5
compiler=/var/tmp/debport-gnome-builder-r1
compat=bubblewrap_0.12.0-1~deb13u1+debport1_arm64.deb
test ! -e "$work"
test -f "$compiler/build/receipts/bubblewrap.json"
mkdir "$work"
cp -a /var/tmp/debport-gta4l-gnome-20261019-r4/rootfs "$work/rootfs"
cp /var/tmp/debport-gta4l-gnome-20261019-r4/userspace-manifest.json "$work/userspace-manifest.json"
cp "$compiler/build/debian-sources/$compat" "$work/$compat"
root=$work/rootfs
cp /etc/resolv.conf "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
mounted=''
cleanup() {
    for name in $mounted; do umount "$root/$name"; done
}
trap cleanup EXIT
for name in dev proc sys; do
    mount --bind "/$name" "$root/$name"
    mounted="$name $mounted"
done
export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8
chroot "$root" apt-get update > "$work/apps.log" 2>&1
chroot "$root" apt-get install -y --no-install-recommends alsa-ucm-conf gnome-snapshot zram-tools >> "$work/apps.log" 2>&1
cleanup
mounted=''
python3 "$repo/tools/integrate-gta4l-gnome.py" --rootfs "$root" \
    --compiler "$compiler" \
    --runtime "$repo/out/recovery-backup-20261018/desktop-runtime.tar" > "$work/integrate.log" 2>&1
python3 "$repo/tools/finalize-gnome-image.py" --work "$work" \
    --credentials "$repo/.cache/keys/debport-gnome-login.json" > "$work/finalize.log" 2>&1
python3 "$repo/tools/package-gnome-device.py" --rootfs "$work/rootfs.ext4" \
    --boot-before "$repo/out/recovery-backup-20261018/boot-debian-headless-r4.img" \
    --output "$repo/out/debian-gnome-r4" --revision 4 > "$work/package.log" 2>&1
cp "$work/debport-gta4l-gnome_0.1.3_arm64.deb" "$work/rootfs-manifest.json" \
   "$work/packages-final.tsv" "$work/userspace-manifest.json" "$work/$compat" "$repo/out/debian-gnome-r4/"
cp "$compiler/build/receipts/bubblewrap.json" "$repo/out/debian-gnome-r4/"
echo GNOME_R4_BUILD_COMPLETE
