#!/sbin/sh
# Stock runtime/code only; no home directories, account files or calibration.
set -eu
loop=''
host=/tmp/dx
cleanup() {
    cd /
    if mountpoint -q "$host"; then umount "$host"; fi
    if [ -n "$loop" ]; then losetup -d "$loop" 2>/dev/null || true; fi
}
trap cleanup EXIT
[ "$(getprop ro.product.device)" = gta4l ]
[ "$(readlink -f /dev/block/by-name/userdata)" = /dev/block/mmcblk0p80 ]
[ -z "$(losetup -j /dev/block/mmcblk0p80)" ]
mkdir -p "$host"
loop=$(losetup -r -o 268435456 -S 23215980032 -fs /dev/block/by-name/userdata)
mount -t ext4 -o ro,noload "$loop" "$host"
cd "$host"
set -- usr/lib/gta4l-camera usr/share/gta4l-sensors usr/lib/gta4l-zink usr/lib/gta4l-kgsl
for path in "$@"; do [ -d "$path" ] && [ ! -L "$path" ]; done
tar -cf - "$@"
