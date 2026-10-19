#!/sbin/sh
# Add a separate Debian file and replace boot. No formatting or repartitioning.
set -eu
OUTFD="$2"
ZIP="$3"
host=/tmp/dh
stage=/tmp/debport-install
loop=''
test_loop=''
pending=''
ui_print() { printf 'ui_print %s\nui_print\n' "$1" > "/proc/self/fd/$OUTFD"; }
fail() { ui_print "Debian install stopped: $1"; exit 1; }
hash_file() { sha256sum "$1" | cut -d ' ' -f 1; }
cleanup() {
    if [ -n "$pending" ] && [ -f "$pending" ]; then rm -f "$pending"; fi
    if mountpoint -q "$stage/root-check" 2>/dev/null; then umount "$stage/root-check"; fi
    if [ -n "$test_loop" ]; then losetup -d "$test_loop" 2>/dev/null || true; fi
    if mountpoint -q "$host"; then umount "$host"; fi
    if [ -n "$loop" ]; then losetup -d "$loop" 2>/dev/null || true; fi
}
trap cleanup EXIT
[ "$(id -u)" = 0 ] || fail 'root recovery required'
[ "$(getprop ro.product.device)" = gta4l ] || fail 'wrong device'
case "$(getprop ro.bootloader)" in T505*) ;; *) fail 'SM-T505 bootloader required';; esac
boot=$(readlink -f /dev/block/by-name/boot)
data=$(readlink -f /dev/block/by-name/userdata)
[ "$boot" = /dev/block/mmcblk0p69 ] && [ "$data" = /dev/block/mmcblk0p80 ] || fail 'partition mapping changed'
[ "$(blockdev --getsize64 "$boot")" = 100663296 ] || fail 'boot size changed'
[ "$(blockdev --getsize64 "$data")" = 23484415488 ] || fail 'userdata size changed'
[ "$(hash_file "$boot")" = @OLD_BOOT_SHA@ ] || fail 'current boot differs from backup'
[ "$(hash_file /dev/block/by-name/recovery)" = @RECOVERY_SHA@ ] || fail 'recovery differs from backup'
mbr_hash=$(dd if="$data" bs=512 count=1 2>/dev/null | sha256sum | cut -d ' ' -f 1)
[ "$mbr_hash" = @MBR_SHA@ ] || fail 'userdata table differs from backup'
[ -z "$(losetup -j "$data")" ] || fail 'userdata already has an active loop mapping'
mkdir -p "$stage" "$host"
unzip -p "$ZIP" boot.img > "$stage/boot.img"
[ "$(wc -c < "$stage/boot.img")" = @NEW_BOOT_BYTES@ ] || fail 'boot image size mismatch'
[ "$(hash_file "$stage/boot.img")" = @NEW_BOOT_SHA@ ] || fail 'boot image checksum mismatch'
unzip -p "$ZIP" recovery-runtime.tar.gz > "$stage/runtime.tar.gz"
[ "$(hash_file "$stage/runtime.tar.gz")" = @FSCK_RUNTIME_SHA@ ] || fail 'filesystem-checker runtime checksum mismatch'
mkdir -p "$stage/runtime"
tar -xzf "$stage/runtime.tar.gz" -C "$stage/runtime" || fail 'filesystem-checker runtime extraction failed'
loop=$(losetup -r -o 268435456 -S 23215980032 -fs "$data") || fail 'root loop setup failed'
"$stage/runtime/usr/lib/ld-musl-aarch64.so.1" --library-path "$stage/runtime/usr/lib" \
    "$stage/runtime/usr/bin/e2fsck" -f -n "$loop" > "$stage/existing-root-fsck.log" 2>&1 \
    || fail 'existing Linux filesystem requires repair; nothing installed'
mount -t ext4 -o ro,noload "$loop" "$host" || fail 'cannot inspect existing Linux root'
grep -Eq '^ID="?(nura|postmarketos)"?$' "$host/etc/os-release" || fail 'existing root identity mismatch'
[ -d "$host/usr/lib/modules/4.19.300-perf" ] || fail 'matching existing kernel modules missing'
available=$(df -k "$host" | tail -1 | awk '{print $4}')
[ "$available" -gt 2621440 ] || fail 'at least 2.5 GiB free space required'
for directory in "$host/var" "$host/var/lib"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail 'unexpected installation directory'
done
directory="$host/var/lib/debport"
resume=${DEBPORT_RESUME_VERIFIED_IMAGE:-0}
if [ "$resume" = 1 ]; then
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail 'resume directory missing or unsafe'
    [ "$(ls -A "$directory" | wc -l)" = 2 ] || fail 'unexpected resume directory contents'
    for file in boot-before-debian.img debian-test-20261018.ext4; do
        [ -f "$directory/$file" ] && [ ! -L "$directory/$file" ] || fail 'unsafe resume file'
    done
    [ "$(hash_file "$directory/boot-before-debian.img")" = @OLD_BOOT_SHA@ ] || fail 'resume boot backup checksum mismatch'
    [ "$(wc -c < "$directory/debian-test-20261018.ext4")" = 1610612736 ] || fail 'resume rootfs size mismatch'
    [ "$(hash_file "$directory/debian-test-20261018.ext4")" = @ROOTFS_SHA@ ] || fail 'resume rootfs checksum mismatch'
else
    [ ! -e "$directory" ] && [ ! -L "$directory" ] || fail 'debport directory already exists; refusing to overwrite'
fi
if [ "${DEBPORT_PREFLIGHT_ONLY:-0}" = 1 ]; then
    ui_print 'Read-only Debian installer preflight passed. No image installed or boot written.'
    exit 0
fi
umount "$host"
losetup -d "$loop" 2>/dev/null || true
loop=''
loop=$(losetup -o 268435456 -S 23215980032 -fs "$data") || fail 'writable root loop setup failed'
mount -t ext4 -o rw "$loop" "$host" || fail 'cannot mount Linux root for the separate Debian file'
ui_print 'Installing a separate Debian command-line/SSH boot test. Existing Linux files are retained.'
if [ "$resume" = 1 ]; then
ui_print 'Resuming with the fully checksum-verified Debian image and original boot backup.'
else
mkdir -m 700 "$directory"
dd if="$boot" of="$directory/boot-before-debian.img" bs=4194304
[ "$(hash_file "$directory/boot-before-debian.img")" = @OLD_BOOT_SHA@ ] || fail 'on-device boot backup failed'
pending="$directory/debian-test-20261018.ext4.partial"
ui_print 'Extracting the 1.5 GiB Debian filesystem file...'
unzip -p "$ZIP" rootfs.ext4 > "$pending" || fail 'rootfs extraction failed'
[ "$(wc -c < "$pending")" = 1610612736 ] || fail 'rootfs size mismatch'
ui_print 'Checking the Debian filesystem checksum...'
[ "$(hash_file "$pending")" = @ROOTFS_SHA@ ] || fail 'rootfs checksum mismatch'
mv "$pending" "$directory/debian-test-20261018.ext4"
pending=''
fi
sync
mkdir -p "$stage/root-check"
test_loop=$(losetup -r -fs "$directory/debian-test-20261018.ext4") || fail 'Debian validation loop setup'
mount -t ext4 -o ro,noload "$test_loop" "$stage/root-check" || fail 'Debian image cannot mount on the device kernel'
grep -q '"device": "samsung-gta4l"' "$stage/root-check/etc/debport-image.json" || fail 'Debian image identity mismatch'
[ "$(chroot "$stage/root-check" /usr/bin/dpkg --print-architecture)" = arm64 ] || fail 'Debian native execution failed'
chroot "$stage/root-check" /lib/systemd/systemd --version || fail 'Debian systemd native execution failed'
chroot "$stage/root-check" /usr/lib/debport-init/ld-musl-aarch64.so.1 --list /usr/lib/debport-init/unudhcpd || fail 'USB DHCP runtime validation failed'
umount "$stage/root-check"
losetup -d "$test_loop" 2>/dev/null || true
test_loop=''
[ "$(hash_file "$boot")" = @OLD_BOOT_SHA@ ] || fail 'boot changed during filesystem installation'
ui_print 'Writing the Debian boot image...'
dd if="$stage/boot.img" of="$boot" bs=4194304 conv=fsync
[ "$(hash_file "$boot")" = @NEW_FULL_BOOT_SHA@ ] || fail 'boot readback mismatch; stay in recovery and use rollback ZIP'
[ "$(hash_file /dev/block/by-name/recovery)" = @RECOVERY_SHA@ ] || fail 'recovery hash changed unexpectedly'
sync
ui_print 'Debian boot test installed and verified. Reboot manually when ready.'
ui_print 'This build has no graphical desktop. USB SSH: debian@172.16.42.1 with the dedicated host key.'
