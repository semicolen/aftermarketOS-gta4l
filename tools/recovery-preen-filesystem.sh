#!/sbin/sh
# Safe automatic metadata repair, with an undo log; no manual yes-to-all mode.
set -eu
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = gta4l ]
[ "$(readlink -f /dev/block/by-name/userdata)" = /dev/block/mmcblk0p80 ]
[ "$(sha256sum /dev/block/by-name/boot | cut -d ' ' -f 1)" = 2834eb30996e647110f2c1f767edb2003b3080cddb0729beaf9d5e6c106b94a0 ]
[ -z "$(losetup -j /dev/block/mmcblk0p80)" ]
loop=$(losetup -o 268435456 -S 23215980032 -fs /dev/block/by-name/userdata)
trap 'losetup -d "$loop" 2>/dev/null || true' EXIT
status=0
/tmp/debport-checker/usr/lib/ld-musl-aarch64.so.1 --library-path /tmp/debport-checker/usr/lib \
    /tmp/debport-checker/usr/bin/e2fsck -f -p -z /tmp/debport-filesystem-forced-preen.e2undo "$loop" || status=$?
echo "Safe automatic checker status: $status"
case "$status" in 0|1) ;; *) exit "$status";; esac
/tmp/debport-checker/usr/lib/ld-musl-aarch64.so.1 --library-path /tmp/debport-checker/usr/lib \
    /tmp/debport-checker/usr/bin/e2fsck -f -n "$loop"
sync
