#!/bin/sh
# Isolated Debian compiler environment; no host packages are installed.
set -eu
root=${1:?Usage: prepare-gnome-compiler.sh /var/tmp/new-builder}
case "$root" in /var/tmp/debport-gnome-builder-*) ;; *) exit 1;; esac
[ ! -e "$root" ]
tools=${2:?Supply the extracted bootstrap-tools sysroot as the second argument}
export DEBOOTSTRAP_DIR="$tools/usr/share/debootstrap"
"$tools/usr/sbin/debootstrap" --arch=amd64 --variant=minbase --include=ca-certificates \
    --keyring="$tools/usr/share/keyrings/debian-archive-keyring.gpg" \
    trixie "$root" https://deb.debian.org/debian
cleanup() { umount "$root/proc"; umount "$root/dev"; }
mount --bind /dev "$root/dev"
mount --bind /proc "$root/proc"
trap cleanup EXIT
cp /etc/resolv.conf "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
cat > "$root/etc/apt/sources.list" <<'EOF'
deb https://deb.debian.org/debian trixie main
deb https://deb.debian.org/debian trixie-updates main
deb https://security.debian.org/debian-security trixie-security main
EOF
chroot "$root" dpkg --add-architecture arm64
chroot "$root" apt-get update
DEBIAN_FRONTEND=noninteractive chroot "$root" apt-get install -y --no-install-recommends \
    crossbuild-essential-arm64 build-essential meson ninja-build pkg-config bison flex \
    python3-mako python3-yaml python3-ply python3-packaging python3-protobuf \
    protobuf-c-compiler protobuf-compiler libwayland-bin gettext patch \
    gobject-introspection libgirepository1.0-dev libglib2.0-dev-bin glslang-tools systemd-dev \
    wayland-protocols spirv-tools:arm64 \
    libdrm-dev:arm64 libelf-dev:arm64 libexpat1-dev:arm64 libvulkan-dev:arm64 \
    zlib1g-dev:arm64 libzstd-dev:arm64 libx11-dev:arm64 libxext-dev:arm64 \
    libxrandr-dev:arm64 libxfixes-dev:arm64 libxshmfence-dev:arm64 \
    libxcb1-dev:arm64 libxcb-icccm4-dev:arm64 libxcb-dri3-dev:arm64 \
    libxcb-present-dev:arm64 libxcb-randr0-dev:arm64 libxcb-shm0-dev:arm64 \
    libxcb-sync-dev:arm64 libxcb-xfixes0-dev:arm64 libwayland-dev:arm64 \
    libwayland-egl-backend-dev:arm64 libx11-xcb-dev:arm64 libxcb-glx0-dev:arm64 \
    libxxf86vm-dev:arm64 libpython3.13-dev:arm64 libdbus-1-dev:arm64 \
    libqrtr-dev:arm64 libqmi-glib-dev:arm64 libmbim-glib-dev:arm64 \
    libgudev-1.0-dev:arm64 libprotobuf-c-dev:arm64 libprotobuf-dev:arm64 \
    libglib2.0-dev:arm64 libpolkit-gobject-1-dev:arm64 libsystemd-dev:arm64 \
    libcap-dev:arm64 liblzma-dev:arm64 libpipewire-0.3-dev:arm64
cat > "$root/usr/local/bin/pkg-config-arm64" <<'EOF'
#!/bin/sh
export PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig
exec /usr/bin/pkg-config "$@"
EOF
chmod 755 "$root/usr/local/bin/pkg-config-arm64"
mkdir -p "$root/build"
cat > "$root/build/arm64.ini" <<'EOF'
[binaries]
c = 'aarch64-linux-gnu-gcc'
cpp = 'aarch64-linux-gnu-g++'
ar = 'aarch64-linux-gnu-ar'
strip = 'aarch64-linux-gnu-strip'
pkg-config = '/usr/local/bin/pkg-config-arm64'
exe_wrapper = '/usr/bin/env'
[host_machine]
system = 'linux'
cpu_family = 'aarch64'
cpu = 'aarch64'
endian = 'little'
[properties]
needs_exe_wrapper = true
EOF
touch "$root/build/compiler-ready"
echo 'Debian native cross compiler is ready.'
