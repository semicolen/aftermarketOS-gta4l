#!/sbin/sh
# Execute the Debian base natively in RAM; no device filesystem is modified.
set -eu
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = gta4l ]
mkdir /tmp/debport-native-smoke
tar -xzf /tmp/debport-native-base.tar.gz -C /tmp/debport-native-smoke
echo 'Recovery kernel:'
uname -a
echo 'Native Debian architecture:'
chroot /tmp/debport-native-smoke /usr/bin/dpkg --print-architecture
echo 'Native Debian systemd version:'
chroot /tmp/debport-native-smoke /lib/systemd/systemd --version
echo 'Native Debian shell and libc:'
chroot /tmp/debport-native-smoke /bin/sh -c 'test -x /sbin/init && /usr/bin/getconf GNU_LIBC_VERSION && /usr/bin/true'
echo 'NATIVE_DEBIAN_SMOKE_PASSED'
