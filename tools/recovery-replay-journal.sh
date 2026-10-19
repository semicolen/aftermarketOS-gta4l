#!/sbin/sh
# Replay only the interrupted journal on the observed nested Linux filesystem.
set -eu
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = gta4l ]
[ "$(readlink -f /dev/block/by-name/userdata)" = /dev/block/mmcblk0p80 ]
[ "$(sha256sum /dev/block/by-name/boot | cut -d ' ' -f 1)" = 2834eb30996e647110f2c1f767edb2003b3080cddb0729beaf9d5e6c106b94a0 ]
[ -z "$(losetup -j /dev/block/mmcblk0p80)" ]
loop=$(losetup -o 268435456 -S 23215980032 -fs /dev/block/by-name/userdata)
trap 'losetup -d "$loop" 2>/dev/null || true' EXIT
checker=/tmp/debport-checker/usr/bin/e2fsck
loader=/tmp/debport-checker/usr/lib/ld-musl-aarch64.so.1
status=0
"$loader" --library-path /tmp/debport-checker/usr/lib "$checker" -p -E journal_only "$loop" || status=$?
case "$status" in 0|1) ;; *) echo "Journal replay stopped with status $status" >&2; exit "$status";; esac
"$loader" --library-path /tmp/debport-checker/usr/lib "$checker" -f -n "$loop"
sync
echo 'Journal replay and subsequent read-only filesystem check passed.'
