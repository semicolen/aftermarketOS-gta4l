#!/sbin/sh
# Add GNOME alongside the successfully booted headless Debian image.
set -eu
OUTFD="$2"
ZIP="$3"
host=/tmp/gh
stage=/tmp/debport-gnome
loop=''
image_loop=''
pending=''
ui_print() { printf 'ui_print %s\nui_print\n' "$1" >> "/proc/self/fd/$OUTFD"; }
fail() { ui_print "GNOME install stopped: $1"; exit 1; }
hash_file() { sha256sum "$1" | cut -d ' ' -f 1; }
cleanup() {
    if [ -n "$pending" ] && [ -f "$pending" ]; then rm -f "$pending"; fi
    if mountpoint -q "$stage/check" 2>/dev/null; then umount "$stage/check"; fi
    if [ -n "$image_loop" ]; then losetup -d "$image_loop" 2>/dev/null || true; fi
    if mountpoint -q "$host" 2>/dev/null; then umount "$host"; fi
    if [ -n "$loop" ]; then losetup -d "$loop" 2>/dev/null || true; fi
}
trap cleanup EXIT
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = gta4l ] || fail 'SM-T505 root recovery required'
case "$(getprop ro.bootloader)" in T505*) ;; *) fail 'SM-T505 bootloader required';; esac
boot=$(readlink -f /dev/block/by-name/boot)
data=$(readlink -f /dev/block/by-name/userdata)
[ "$boot" = /dev/block/mmcblk0p69 ] && [ "$data" = /dev/block/mmcblk0p80 ] || fail 'partition mapping changed'
[ "$(blockdev --getsize64 "$boot")" = 100663296 ] || fail 'boot partition size changed'
[ "$(blockdev --getsize64 "$data")" = 23484415488 ] || fail 'userdata size changed'
[ "$(hash_file "$boot")" = @OLD_BOOT_SHA@ ] || fail 'current boot differs from successful Debian test'
[ "$(hash_file /dev/block/by-name/recovery)" = @RECOVERY_SHA@ ] || fail 'recovery differs from backup'
[ "$(dd if="$data" bs=512 count=1 2>/dev/null | sha256sum | cut -d ' ' -f 1)" = @MBR_SHA@ ] || fail 'partition table changed'
[ -z "$(losetup -j "$data")" ] || fail 'userdata already has a loop mapping'
mkdir -p "$stage" "$host" "$stage/check" "$stage/runtime"
unzip -p "$ZIP" boot.img > "$stage/boot.img"
[ "$(wc -c < "$stage/boot.img")" = @NEW_BOOT_BYTES@ ] && [ "$(hash_file "$stage/boot.img")" = @NEW_BOOT_SHA@ ] || fail 'new boot checksum or size mismatch'
unzip -p "$ZIP" recovery-runtime.tar.gz > "$stage/runtime.tar.gz"
[ "$(hash_file "$stage/runtime.tar.gz")" = @FSCK_RUNTIME_SHA@ ] || fail 'checker runtime checksum mismatch'
tar -xzf "$stage/runtime.tar.gz" -C "$stage/runtime"
check_fs() {
    "$stage/runtime/usr/lib/ld-musl-aarch64.so.1" --library-path "$stage/runtime/usr/lib" \
        "$stage/runtime/usr/bin/e2fsck" -f -n "$1"
}
loop=$(losetup -r -o 268435456 -S 23215980032 -fs "$data")
check_fs "$loop" > "$stage/host-fsck.log" 2>&1 || fail 'existing filesystem needs repair; no installation writes performed'
mount -t ext4 -o ro,noload "$loop" "$host"
grep -Eq '^ID="?(nura|postmarketos)"?$' "$host/etc/os-release" || fail 'original host filesystem identity mismatch'
directory="$host/var/lib/debport"
for parent in "$host/var" "$host/var/lib"; do
    [ -d "$parent" ] && [ ! -L "$parent" ] || fail 'unsafe host parent directory'
done
[ -d "$directory" ] && [ ! -L "$directory" ] || fail 'existing Debian directory missing or unsafe'
[ -f "$directory/debian-test-20261018.ext4" ] && [ ! -L "$directory/debian-test-20261018.ext4" ] || fail 'successful headless Debian image missing'
[ "$(wc -c < "$directory/debian-test-20261018.ext4")" = 1610612736 ] || fail 'headless image size changed'
[ -f "$directory/boot-before-debian.img" ] && [ ! -L "$directory/boot-before-debian.img" ] || fail 'unsafe original boot backup'
[ "$(hash_file "$directory/boot-before-debian.img")" = @ORIGINAL_BOOT_SHA@ ] || fail 'original boot backup mismatch'
available=$(df -k "$host" | tail -1 | awk '{print $4}')
[ "$available" -gt @NEEDED_KIB@ ] || fail 'insufficient space for separate GNOME image'
image="$directory/gnome-20261018.ext4"
backup="$directory/boot-before-gnome.img"
resume=${DEBPORT_RESUME_VERIFIED_IMAGE:-0}
if [ "$resume" = 1 ]; then
    [ -f "$image" ] && [ ! -L "$image" ] && [ -f "$backup" ] && [ ! -L "$backup" ] || fail 'unsafe resume files'
    [ "$(hash_file "$backup")" = @OLD_BOOT_SHA@ ] || fail 'resume boot backup mismatch'
    [ "$(wc -c < "$image")" = @ROOTFS_BYTES@ ] && [ "$(hash_file "$image")" = @ROOTFS_SHA@ ] || fail 'resume image mismatch'
else
    [ ! -e "$image" ] && [ ! -L "$image" ] && [ ! -e "$backup" ] && [ ! -L "$backup" ] || fail 'GNOME files already exist; refusing overwrite'
    [ ! -e "$image.partial" ] && [ ! -L "$image.partial" ] || fail 'partial GNOME image already exists; refusing overwrite'
fi
if [ "${DEBPORT_PREFLIGHT_ONLY:-0}" = 1 ]; then
    ui_print 'GNOME read-only preflight passed. No image installed or boot written.'
    exit 0
fi
umount "$host"
losetup -d "$loop" 2>/dev/null || true
loop=$(losetup -o 268435456 -S 23215980032 -fs "$data")
mount -t ext4 -o rw "$loop" "$host"
if [ "$resume" != 1 ]; then
    ui_print 'Preserving working headless Debian and installing a separate GNOME image...'
    dd if="$boot" of="$backup" bs=4194304
    [ "$(hash_file "$backup")" = @OLD_BOOT_SHA@ ] || fail 'headless boot backup failed'
    pending="$image.partial"
    (
        for entry in @ROOTFS_ENTRIES@; do
            unzip -p "$ZIP" "$entry" || exit 1
        done
    ) > "$pending" || fail 'chunk extraction failed'
    [ "$(wc -c < "$pending")" = @ROOTFS_BYTES@ ] && [ "$(hash_file "$pending")" = @ROOTFS_SHA@ ] || fail 'GNOME filesystem size or checksum mismatch'
    mv "$pending" "$image"
    pending=''
    sync
fi
ui_print 'Validating the GNOME filesystem and native Debian programs...'
image_loop=$(losetup -r -fs "$image") || fail 'GNOME image loop setup failed'
check_fs "$image_loop" > "$stage/gnome-fsck.log" 2>&1 || fail 'GNOME filesystem failed its check'
mount -t ext4 -o ro,noload "$image_loop" "$stage/check"
grep -q '"desktop": "gnome"' "$stage/check/etc/debport-image.json" || fail 'wrong image identity'
[ "$(chroot "$stage/check" /usr/bin/dpkg --print-architecture)" = arm64 ] || fail 'native Debian execution failed'
chroot "$stage/check" /usr/bin/gnome-shell --version || fail 'GNOME native execution failed'
chroot "$stage/check" /lib/ld-linux-aarch64.so.1 --list /usr/lib/gta4l-kgsl/libvulkan_freedreno.so || fail 'GPU runtime dependencies missing'
chroot "$stage/check" /usr/bin/env LD_LIBRARY_PATH=/usr/lib/debport-device/lib PD_MAPPER_FW_DIR=/lib/firmware/postmarketos \
    /usr/lib/debport-device/bin/pd-mapper --check-maps || fail 'stock DSP manifest validation failed'
umount "$stage/check"
losetup -d "$image_loop" 2>/dev/null || true
image_loop=''
[ "$(hash_file "$boot")" = @OLD_BOOT_SHA@ ] || fail 'boot changed during installation'
ui_print 'Writing the GNOME boot image...'
dd if="$stage/boot.img" of="$boot" bs=4194304 conv=fsync
[ "$(hash_file "$boot")" = @NEW_FULL_BOOT_SHA@ ] || fail 'boot readback mismatch; stay in recovery'
[ "$(hash_file /dev/block/by-name/recovery)" = @RECOVERY_SHA@ ] || fail 'recovery unexpectedly changed'
sync
ui_print 'Debian GNOME installed and verified. Reboot manually when ready.'
ui_print 'Local login: user / 147147'
