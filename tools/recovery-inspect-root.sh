#!/sbin/sh
# Read the existing nested Linux filesystem; never replay its journal.
set -eu
loop=''
cleanup() {
    if mountpoint -q /tmp/debport-inspect; then umount /tmp/debport-inspect; fi
    if [ -n "$loop" ]; then losetup -d "$loop" 2>/dev/null || true; fi
}
trap cleanup EXIT
[ "$(getprop ro.product.device)" = gta4l ]
[ "$(readlink -f /dev/block/by-name/userdata)" = /dev/block/mmcblk0p80 ]
mkdir -p /tmp/debport-inspect
loop=$(losetup -r -o 268435456 -S 23215980032 -fs /dev/block/by-name/userdata)
mount -t ext4 -o ro,noload "$loop" /tmp/debport-inspect
cat /tmp/debport-inspect/etc/os-release
df -k /tmp/debport-inspect
ls -ld /tmp/debport-inspect/usr/lib/modules /tmp/debport-inspect/lib/modules
ls /tmp/debport-inspect/usr/lib/modules
ls -ld /tmp/debport-inspect/var/lib /tmp/debport-inspect/boot
ls -l /tmp/debport-inspect/boot
if [ -e /tmp/debport-inspect/var/lib/debport ]; then
    ls -l /tmp/debport-inspect/var/lib/debport
else
    echo 'No Debian installation directory exists.'
fi
command -v e2fsck || true
command -v tune2fs || true
command -v chroot || true
