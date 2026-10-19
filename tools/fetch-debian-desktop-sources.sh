#!/bin/sh
set -eu
root=${1:?Supply isolated Debian compiler directory}
[ -f "$root/build/compiler-ready" ]
printf 'deb-src https://deb.debian.org/debian trixie main\ndeb-src https://security.debian.org/debian-security trixie-security main\n' > "$root/etc/apt/sources.list.d/device-sources.list"
chroot "$root" apt-get update
mkdir -p "$root/build/debian-sources"
chroot "$root" /usr/bin/env -C /build/debian-sources apt-get source --download-only modemmanager gnome-control-center bubblewrap
for source in "$root"/build/debian-sources/*.dsc; do
    name=${source##*/}
    chroot "$root" /usr/bin/env -C /build/debian-sources dpkg-source -x "$name"
done
# The locale generator runs on the build machine during cross compilation.
chroot "$root" python3 -c 'from pathlib import Path; p=Path("/build/debian-sources/gnome-control-center-48.4/debian/control"); s=p.read_text(); assert s.count("               locales,")==1; p.write_text(s.replace("               locales,", "               locales:native,"))'
DEBIAN_FRONTEND=noninteractive chroot "$root" /usr/bin/env -C /build/debian-sources/gnome-control-center-48.4 \
    apt-get build-dep -y --no-install-recommends -a arm64 -P nocheck .
DEBIAN_FRONTEND=noninteractive chroot "$root" \
    apt-get build-dep -y --no-install-recommends -a arm64 -P nocheck bubblewrap
