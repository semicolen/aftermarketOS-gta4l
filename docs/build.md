# Staged GNOME build

Clone recursively. The `builder` submodule supplies the shared `debport`
Python modules. Device tools add it to their import path. All rootfs and compiler
work must run as root on native Linux storage, with ARM64 QEMU binfmt available
when building on amd64. Several tens of GiB are needed. The Windows checkout
may store scripts and final archives, but not unpacked Linux filesystems.

The initial port uses verified kernel/firmware exports from an already working
SM-T505 installation. It does not yet automate installing from stock Android
or rebuilding the kernel in a Debian package. The public firmware/runtime
assets contain stock code, not calibration, modem NV state or user files.
Check release SHA256SUMS before extracting them.

## Base and matching hardware

```sh
export PYTHONPATH="$PWD/builder"
sudo -E sh builder/tools/build-local.sh /var/tmp/aftermarketos-base "$PWD/profiles/samsung-gta4l.json"
```

Use the resulting `rootfs.tar.xz`. Prepare a dedicated SSH public key for your
own development image. The public-image stage removes it before redistribution.
The firmware archive decompresses to the original `hardware.tar` and must match
SHA256 `4d3ae5a04f72c2d41feade4f47d834e70e0ed3688e82634ca02f6ea389972ad8`.
The boot input is the pinned original port's boot image; never substitute an
Android stock kernel or mismatched modules. Obtain your own boot/recovery backup
using `tools/backup-device-boot.py` before attempting installation.

```sh
sudo -E python3 tools/prepare-device-rootfs.py \
  --base /path/to/rootfs.tar.xz --base-sha256 ACTUAL_VERIFIED_BASE_SHA256 \
  --hardware /path/to/hardware.tar --boot /path/to/matching-original-port-boot.img \
  --public-key /path/to/development-key.pub --output /var/tmp/aftermarketos-headless
sudo -E python3 tools/prepare-gnome-userspace.py \
  --prepared-base /var/tmp/aftermarketos-headless/rootfs --output /var/tmp/aftermarketos-gnome
```

The rebuilt base hash is an explicit input because Debian repositories change.
The hardware archive remains pinned. The base builder's output is not a
flashable image by itself.

## Debian compiler and adaptations

```sh
sudo sh builder/tools/bootstrap-tools.sh /var/tmp/aftermarketos-bootstrap
sudo sh tools/prepare-gnome-compiler.sh /var/tmp/debport-gnome-builder-new \
  /var/tmp/aftermarketos-bootstrap/sysroot
python3 tools/fetch-gta4l-sources.py --output /var/tmp/aftermarketos-sources
sudo sh tools/fetch-debian-desktop-sources.sh /var/tmp/debport-gnome-builder-new
sudo python3 tools/build-gta4l-debian-components.py \
  --builder /var/tmp/debport-gnome-builder-new --sources /var/tmp/aftermarketos-sources
sudo python3 tools/build-bubblewrap-compat.py --builder /var/tmp/debport-gnome-builder-new
```

The component builder verifies upstream source/patch checksums. Debian source
packages come through signed APT indexes. The original source archives and
patched Debian source trees used for the release are also supplied as release
assets. Current APT versions may differ from the recorded ones; use the included
source bundle for the exact component revisions rather than assuming a later
build has identical inputs. The compiler configuration currently targets amd64
hosts cross-building arm64.

Decompress the desktop-runtime asset to `desktop-runtime.tar`, SHA256
`a1ec91dcf156aab08aa8dad5b6d8a83a1db81e4300149979cd3edf0bd614afb6`.

```sh
sudo -E python3 tools/integrate-gta4l-gnome.py \
  --rootfs /var/tmp/aftermarketos-gnome/rootfs --compiler /var/tmp/debport-gnome-builder-new \
  --runtime /path/to/desktop-runtime.tar
sudo cp /var/tmp/debport-gnome-builder-new/build/debian-sources/bubblewrap_0.12.0-1~deb13u1+debport1_arm64.deb \
  /var/tmp/aftermarketos-gnome/
sudo -E python3 tools/finalize-gnome-image.py --work /var/tmp/aftermarketos-gnome
sudo python3 tools/prepare-public-image.py --prepared /var/tmp/aftermarketos-gnome \
  --output /var/tmp/aftermarketos-public
```

`finalize-gnome-image.py` installs the device/compatibility packages, configures
`user` / `147147`, validates native dependencies and services, clears host keys
and machine ID, and writes a 6 GiB ext4 image. Public preparation accepts only
a pristine build, refuses personal home/network/runtime state, removes the
development authorized key and revalidates the image. It never reads a live
tablet root or its backup.

## Recovery package

```sh
sudo -E python3 tools/package-gnome-device.py \
  --rootfs /var/tmp/aftermarketos-public/rootfs.ext4 \
  --boot-before /path/to/verified-headless-boot.img \
  --headless-manifest releases/r5/headless-prerequisites.json \
  --recovery-runtime /path/to/recovery-runtime.tar.gz \
  --output /var/tmp/aftermarketos-release --revision 5
```

The predecessor boot must match the manifest's full-partition hash. The
installer's exact device, boot, recovery, partition-table and filesystem
checks are retained. It is intentionally specific to the verified existing
layout. Historical incremental build scripts are retained as build history;
the commands above expose their previously local inputs.
