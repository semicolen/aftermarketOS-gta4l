#!/bin/sh
# Assemble the verified modem/WLAN bring-up and GPS test applications.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=/var/tmp/debport-gta4l-gnome-20261019-r4
test ! -e "$work"
mkdir "$work"
cp -a /var/tmp/debport-gta4l-gnome-20261018-r3/rootfs "$work/rootfs"
cp /var/tmp/debport-gta4l-gnome-20261018-r3/userspace-manifest.json "$work/userspace-manifest.json"
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
chroot "$root" apt-get install -y --no-install-recommends gnome-maps systemd-timesyncd libqmi-utils >> "$work/apps.log" 2>&1
cleanup
mounted=''
python3 "$repo/tools/integrate-gta4l-gnome.py" --rootfs "$root" \
    --compiler /var/tmp/debport-gnome-builder-r1 \
    --runtime "$repo/out/recovery-backup-20261018/desktop-runtime.tar" > "$work/integrate.log" 2>&1
mkdir -p "$repo/out/modem-bringup"
cp "$work/debport-gta4l-gnome_0.1.2_arm64.deb" "$repo/out/modem-bringup/"
python3 "$repo/tools/finalize-gnome-image.py" --work "$work" \
    --credentials "$repo/.cache/keys/debport-gnome-login.json" > "$work/finalize.log" 2>&1
python3 "$repo/tools/package-gnome-device.py" --rootfs "$work/rootfs.ext4" \
    --boot-before "$repo/out/recovery-backup-20261018/boot-debian-headless-r4.img" \
    --output "$repo/out/debian-gnome-r3" --revision 3 > "$work/package.log" 2>&1
cp "$work/debport-gta4l-gnome_0.1.2_arm64.deb" "$work/rootfs-manifest.json" \
   "$work/packages-final.tsv" "$work/userspace-manifest.json" "$repo/out/debian-gnome-r3/"
echo GNOME_R3_BUILD_COMPLETE
