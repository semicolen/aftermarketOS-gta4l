# GNOME r5 public preview

Debian 13 (trixie), GNOME Shell 48.7, downstream Linux 4.19.300-perf
#11-postmarketOS, device package 0.1.4. This release follows the r5 physical
boot test on SM-T505 on 19 October 2026.

Local GNOME login and sudo: **`user` / `147147`**. GNOME auto-login is enabled.
The public image has no development SSH authorized key, SSH host keys or shared
machine ID. USB networking is configured at 172.16.42.1, but SSH requires your
own public key to be added locally to `/home/user/.ssh/authorized_keys`, owned
by user and mode 0600. Password SSH and root login remain disabled.

## Installer prerequisites

The OrangeFox ZIP supports the existing **verified headless Debian/Nura layout**
used during this port's bring-up. It is not a stock-Android installer or a
general SM-T505 installation path. Do not change its hashes to bypass checks.

- SM-T505 / gta4l, the expected bootloader family and partition mapping.
- Boot partition p69 (100663296 bytes), userdata p80 (23484415488 bytes).
- Nested original Linux ext4 filesystem at offset 268435456, size 23215980032.
- Existing `/var/lib/debport/debian-test-20261018.ext4` (1.5 GiB), verified
  original boot backup, and the exact headless boot, OrangeFox and partition-table
  hashes in `headless-prerequisites.json`.
- Sufficient free space for a separate 6 GiB GNOME image and recovery workspace.
- No existing GNOME image at `/var/lib/debport/gnome-20261018.ext4`.

The package keeps the original Linux filesystem, headless Debian image and
OrangeFox, and does no formatting or repartitioning. It verifies eight rootfs
chunks and the complete image, runs filesystem/native userspace checks, backs
up the current boot and changes boot only after those checks pass. The rollback
ZIP restores the preserved working headless boot; it does not erase user data.

Verify downloads with `sha256sum -c SHA256SUMS`. Copy the installer to persistent
storage accessible to OrangeFox and use Install, keeping the archive off its
RAM-backed `/tmp`. Earlier sideload attempts restarted recovery; this release
does not claim that sideload path is fixed.

Existing GNOME installations need a separate backup-and-migration procedure.
The test tablet was upgraded that way and is already on r5; the preview ZIP
will intentionally refuse to overwrite it.

## Validation and limits

The r5 base with privately migrated user data reached the GNOME desktop. The
user confirmed it, and SSH verified the renamed account and fresh sudo
authentication, native Turnip/Zink libraries and GPU device access, Wi-Fi
reconnection, speaker/microphone endpoints, zram and hardware services.
Earlier user tests confirmed touch, rotation, Bluetooth, hardware GPS in Maps,
speaker playback, and GNOME Camera photographs/gallery/mic/video.

The downloadable public derivative removes the development authorized key and
resets build identity/logs from the pristine, never-booted tree. Its native
userspace, systemd units, filesystem, reconstructed rootfs hash and ZIP CRCs
were checked offline. **That exact derivative has not been flashed.** See
`device-verification.json`; metadata does not claim an exact-image boot test.

Known gaps: one failed suspend attempt on r5; deep sleep/resume is unresolved.
Cellular data/registration, headset routing and Bluetooth audio are untested
on Debian. The modem uses read-only physical NV storage. Standard camera
streams are 640x480, and long recording stability needs more testing. USB
can disconnect intermittently.

## Assets

- `aftermarketOS-gta4l-GNOME-r5-public.zip`: guarded preview installer.
- `SM-T505-restore-working-headless-Debian.zip`: exact headless boot rollback.
- `hardware.tar.xz`: matching kernel modules and stock early/radio firmware.
- `desktop-runtime.tar.xz`: stock camera/sensor runtime and original port inputs.
- `headless-predecessor-boot.img.gz`, `recovery-runtime.tar.gz`: packaging inputs.
- Device and Bubblewrap `.deb` packages, package inventory, image/installer
  manifests and `SHA256SUMS`.
- Component source bundle and pinned kernel source archive. Integration
  patches, kernel config and build recipes are in the pinned source submodules
  and source bundle. [Provenance and licenses](../../docs/provenance.md).

Stock firmware/runtime retains its original Samsung/Qualcomm terms. No user
media, saved network profiles, modem NV storage, personal calibration, device
serial, private keys or raw device backups are release assets.
