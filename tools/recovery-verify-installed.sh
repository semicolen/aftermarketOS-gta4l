#!/sbin/sh
# Read-only verification of revision 4 on the identified SM-T505.
set -eu
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = gta4l ]
hash_file() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(hash_file /dev/block/by-name/boot)" = a958939a7ea3adedd9a3d1a5d6156eb8406a50359477b1dd57e20352d76bd3ee ]
[ "$(hash_file /dev/block/by-name/recovery)" = 5d427f6f7ac3fd61b9f0d5aad21ef7404464ab3ed6f8b972151149b52552ad98 ]
[ "$(dd if=/dev/block/mmcblk0p80 bs=512 count=1 2>/dev/null | sha256sum | cut -d ' ' -f 1)" = caa45bcb7793964815a2fdb812bfc72addbd51ab8ab1b790dd57ebf94b908c62 ]
[ -z "$(losetup -j /dev/block/mmcblk0p80)" ]
host=/tmp/dv
loop=''
image_loop=''
cleanup() {
    if [ -n "$image_loop" ]; then losetup -d "$image_loop" 2>/dev/null || true; fi
    if mountpoint -q "$host"; then umount "$host"; fi
    if [ -n "$loop" ]; then losetup -d "$loop" 2>/dev/null || true; fi
}
trap cleanup EXIT
check_fs() {
    /tmp/debport-install/runtime/usr/lib/ld-musl-aarch64.so.1 \
        --library-path /tmp/debport-install/runtime/usr/lib \
        /tmp/debport-install/runtime/usr/bin/e2fsck -f -n "$1"
}
loop=$(losetup -r -o 268435456 -S 23215980032 -fs /dev/block/mmcblk0p80)
check_fs "$loop"
mkdir -p "$host"
mount -t ext4 -o ro,noload "$loop" "$host"
directory="$host/var/lib/debport"
[ -d "$directory" ] && [ ! -L "$directory" ]
[ "$(ls -A "$directory" | wc -l)" = 2 ]
for file in boot-before-debian.img debian-test-20261018.ext4; do
    [ -f "$directory/$file" ] && [ ! -L "$directory/$file" ]
done
[ "$(hash_file "$directory/boot-before-debian.img")" = 2834eb30996e647110f2c1f767edb2003b3080cddb0729beaf9d5e6c106b94a0 ]
[ "$(wc -c < "$directory/debian-test-20261018.ext4")" = 1610612736 ]
[ "$(hash_file "$directory/debian-test-20261018.ext4")" = cd819cccdda5e743e4ed9a49037ae09da69e9eab1edab5bf60abc52185de4792 ]
image_loop=$(losetup -r -fs "$directory/debian-test-20261018.ext4")
check_fs "$image_loop"
echo 'INSTALLATION_VERIFIED: boot, recovery, partition table, original boot backup, Debian image and both filesystems.'
