#!/sbin/sh
# Remove only the two verified files created by the interrupted Debian attempt.
set -eu
loop=''
host=/tmp/debport-cleanup-host
cleanup() {
    if mountpoint -q "$host" 2>/dev/null; then umount "$host"; fi
    if [ -n "$loop" ]; then losetup -d "$loop" 2>/dev/null || true; fi
}
trap cleanup EXIT
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = gta4l ]
[ "$(readlink -f /dev/block/by-name/userdata)" = /dev/block/mmcblk0p80 ]
[ "$(sha256sum /dev/block/by-name/boot | cut -d ' ' -f 1)" = 2834eb30996e647110f2c1f767edb2003b3080cddb0729beaf9d5e6c106b94a0 ]
mkdir -p /tmp/debport-checker "$host"
unzip -p /tmp/debport-test.zip recovery-runtime.tar.gz > /tmp/debport-checker/runtime.tar.gz
tar -xzf /tmp/debport-checker/runtime.tar.gz -C /tmp/debport-checker
loop=$(losetup -r -o 268435456 -S 23215980032 -fs /dev/block/by-name/userdata)
/tmp/debport-checker/usr/lib/ld-musl-aarch64.so.1 --library-path /tmp/debport-checker/usr/lib \
    /tmp/debport-checker/usr/bin/e2fsck -f -n "$loop"
mount -t ext4 -o ro,noload "$loop" "$host"
directory="$host/var/lib/debport"
check_files() {
    [ -d "$directory" ] && [ ! -L "$directory" ]
    [ "$(ls -A "$directory" | wc -l)" = 2 ]
    [ -f "$directory/boot-before-debian.img" ] && [ ! -L "$directory/boot-before-debian.img" ]
    [ "$(sha256sum "$directory/boot-before-debian.img" | cut -d ' ' -f 1)" = 2834eb30996e647110f2c1f767edb2003b3080cddb0729beaf9d5e6c106b94a0 ]
    [ -f "$directory/debian-test-20261018.ext4.partial" ] && [ ! -L "$directory/debian-test-20261018.ext4.partial" ]
    [ "$(wc -c < "$directory/debian-test-20261018.ext4.partial")" = 0 ]
}
check_files
umount "$host"
losetup -d "$loop" 2>/dev/null || true
loop=$(losetup -o 268435456 -S 23215980032 -fs /dev/block/by-name/userdata)
mount -t ext4 -o rw "$loop" "$host"
check_files
rm "$directory/debian-test-20261018.ext4.partial" "$directory/boot-before-debian.img"
rmdir "$directory"
sync
echo 'Only the verified empty attempt and duplicate boot backup were removed. Original boot remains unchanged.'
