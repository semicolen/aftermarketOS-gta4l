#!/sbin/sh
# Apply the first-boot corrections to an already checked, mounted preview.
set -eu
root=/tmp/gimg
test "$(id -u)" = 0
test "$(getprop ro.product.device)" = gta4l
test "$(sha256sum /dev/block/by-name/boot | cut -d ' ' -f 1)" = 5b493c01d417a4a8a9b4ebf4ecc3e3ddffa7ccc0541c9b3671598d563cefa271
mountpoint -q "$root"
test -f "$root/tmp/apply-gnome-startup-fix.py"
test ! -e "$root/usr/sbin/policy-rc.d"
cleanup() {
    cd /
    for name in sys proc dev; do
        mountpoint -q "$root/$name" && umount "$root/$name" || true
    done
    rm -f "$root/usr/sbin/policy-rc.d"
}
trap cleanup EXIT
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
for name in dev proc sys; do mount --bind "/$name" "$root/$name"; done
native() { chroot "$root" /usr/bin/env PATH=/usr/sbin:/usr/bin:/sbin:/bin DEBIAN_FRONTEND=noninteractive "$@"; }
native /usr/bin/python3 /tmp/apply-gnome-startup-fix.py --rootfs /
native /bin/sh -c '/usr/bin/dpkg --install /tmp/gnome-extra-debs/*.deb'
native /usr/bin/dpkg --audit
native /usr/bin/systemd-analyze --man=no verify gta4l-qrtr.service gta4l-modem.service gta4l-bluetooth.service NetworkManager.service gdm3.service
sync
echo GNOME_STARTUP_R2_APPLIED
