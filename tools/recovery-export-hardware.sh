#!/sbin/sh
set -eu
loop=''
cleanup() {
    if mountpoint -q /tmp/debport-export; then umount /tmp/debport-export; fi
    if [ -n "$loop" ]; then losetup -d "$loop" 2>/dev/null || true; fi
}
trap cleanup EXIT
[ "$(getprop ro.product.device)" = gta4l ]
[ "$(readlink -f /dev/block/by-name/userdata)" = /dev/block/mmcblk0p80 ]
mkdir -p /tmp/debport-export
loop=$(losetup -r -o 268435456 -S 23215980032 -fs /dev/block/by-name/userdata)
mount -t ext4 -o ro,noload "$loop" /tmp/debport-export
tar -C /tmp/debport-export -cf - usr/lib/modules/4.19.300-perf usr/lib/firmware/postmarketos
