#!/bin/busybox ash
# Experimental Debian root in a separate file on the existing Linux filesystem.
# The kernel, drivers, DTBs and early firmware are retained from the verified boot.
. /init_functions.sh
. /init_functions_2nd.sh

fail_debian() {
    echo "debport: $*" > /dev/kmsg
    echo "Debian boot stopped: $*"
    echo 'Return to OrangeFox and use the supplied boot rollback ZIP.'
    while :; do sleep 60; done
}

echo 'debport: preparing Debian boot test' > /dev/kmsg
setup_udev
load_modules /lib/modules/initramfs.load
setup_usb_network
start_unudhcpd

mkdir -p /run
mountpoint -q /run || mount -t tmpfs -o mode=0755,nosuid,nodev tmpfs /run || fail_debian 'cannot mount /run'
mkdir -p /run/initramfs/dh
chmod 700 /run/initramfs

# Geometry is from the backed-up userdata MBR and is checked again by the installer.
host_loop=$(losetup --find --show --offset 268435456 --sizelimit 23215980032 /dev/mmcblk0p80) || fail_debian 'userdata loop setup'
mount -t ext4 -o rw "$host_loop" /run/initramfs/dh || fail_debian 'existing Linux root mount'
image=/run/initramfs/dh/var/lib/debport/debian-test-20261018.ext4
[ -f "$image" ] && [ ! -L "$image" ] || fail_debian 'Debian image missing'
debian_loop=$(losetup --find --show "$image") || fail_debian 'Debian loop setup'
mount -t ext4 -o rw "$debian_loop" /sysroot || fail_debian 'Debian root mount'
[ -x /sysroot/usr/lib/systemd/systemd ] || fail_debian 'Debian systemd missing'
grep -q '"device": "samsung-gta4l"' /sysroot/etc/debport-image.json || fail_debian 'wrong Debian image identity'

mkdir -p /sysroot/run
cp /pmOS_init.log /run/debport-initramfs.log 2>/dev/null || true
dmesg > /run/debport-pre-handoff.log
cat /proc/cmdline > /run/debport-cmdline.txt
mount --move /run /sysroot/run || fail_debian 'preserve backing filesystem mount'
killall udevd syslogd unudhcpd 2>/dev/null || true
rm -f /dev/log
echo 'debport: switching to Debian systemd' > /dev/kmsg
sync
exec >/dev/console 2>&1
exec switch_root /sysroot /sbin/init
fail_debian 'switch_root returned'
