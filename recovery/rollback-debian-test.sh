#!/sbin/sh
set -eu
OUTFD="$2"
ZIP="$3"
ui_print() { printf 'ui_print %s\nui_print\n' "$1" > "/proc/self/fd/$OUTFD"; }
fail() { ui_print "Rollback stopped: $1"; exit 1; }
hash_file() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = gta4l ] || fail 'SM-T505 root recovery required'
boot=$(readlink -f /dev/block/by-name/boot)
[ "$boot" = /dev/block/mmcblk0p69 ] && [ "$(blockdev --getsize64 "$boot")" = 100663296 ] || fail 'unexpected boot partition'
[ "$(hash_file "$boot")" = @NEW_FULL_BOOT_SHA@ ] || fail 'boot differs from the Debian test image'
[ "$(hash_file /dev/block/by-name/recovery)" = @RECOVERY_SHA@ ] || fail 'recovery changed'
mkdir -p /tmp/debport-rollback
unzip -p "$ZIP" boot-before.img > /tmp/debport-rollback/boot.img
[ "$(wc -c < /tmp/debport-rollback/boot.img)" = 100663296 ] || fail 'backup length mismatch'
[ "$(hash_file /tmp/debport-rollback/boot.img)" = @OLD_BOOT_SHA@ ] || fail 'backup checksum mismatch'
dd if=/tmp/debport-rollback/boot.img of="$boot" bs=4194304 conv=fsync
[ "$(hash_file "$boot")" = @OLD_BOOT_SHA@ ] || fail 'rollback readback failed'
sync
ui_print 'Original boot restored and verified. Existing Linux will boot again; Debian file retained.'
