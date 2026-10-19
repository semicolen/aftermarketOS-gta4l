#!/bin/sh
# Update the existing local preview tree without starting device services.
set -eu
root=${1:?Supply the offline rootfs directory}
export_dir=${2:?Supply a new package export directory}
test -f "$root/etc/debport-image.json"
cp /etc/resolv.conf "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8
chroot "$root" apt-get update
chroot "$root" apt-get -y --download-only --no-install-recommends install wpasupplicant wireless-regdb libpam-gnome-keyring
test ! -e "$export_dir"
mkdir -p "$export_dir"
cp "$root"/var/cache/apt/archives/*.deb "$export_dir/"
chroot "$root" apt-get -y --no-install-recommends install wpasupplicant wireless-regdb libpam-gnome-keyring
rm "$root/usr/sbin/policy-rc.d"
