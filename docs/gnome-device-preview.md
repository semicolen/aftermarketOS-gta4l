# Debian GNOME preview for SM-T505

Debian 13's GNOME 48 boots on the SM-T505 using the existing downstream kernel
`4.19.300-perf #11-postmarketOS`. The user confirmed the visible desktop, and
USB SSH verified the native Debian system. GNOME Shell maps the rebuilt
Turnip/Zink libraries and holds `/dev/kgsl-3d0` and `/dev/dri/card0` open.
The startup services run successfully. The r5 reboot recorded one failed
suspend attempt; deep sleep/resume remains unresolved.

The user reports working touch, rotation, camera and Bluetooth. BlueZ also
detects the powered controller, and the patched sensor service reports an
accelerometer and orientation. Speaker playback and microphone capture are
now confirmed. GNOME Camera (Snapshot 48.0.1) saves photographs, loads its
gallery and records video after the [audio/camera corrections](audio-camera-debug.md).
Headset routing and Bluetooth audio have not been tested.

Wi-Fi now connects to the internet and reconnects automatically after reboot.
The user confirmed a successful connection; HTTPS access was independently
verified. RMTFS, modem, IPA, WLAN, ModemManager and GPS assistance all start
through persistent services. The modem remains online with zero crashes.
ModemManager detects raw GPS, NMEA and XTRA assistance support. With GNOME
Location Services enabled, Maps receives hardware GPS through GeoClue.
The receiver reported a checksum-valid RMC sentence with an active fix only
0.75 seconds old, and the user confirmed the correct position in Maps.
Coordinates and raw NMEA were not logged. The user saw an incorrect initial
position that resolved after retrying; its cause is unconfirmed. Cellular
data and registration are not claimed as working.

The first graphical boot hit a modem subsystem panic because RMTFS could not
open its shared-memory device. Debian expects `/dev/qcom_rmtfs_uio1`; the
kernel exposes `/dev/uio0` with the name `rmtfs`. A matching udev rule now
creates the alias. The modem waits until RMTFS has mapped that device and
registered QRTR service 14, then exposes its own QMI control service before
IPA and WLAN start. RMTFS uses `-P -r`, keeping NV writes in memory. Private
backups of modemst1, modemst2, fsg and fsc were verified, and all four physical
partitions remained unchanged after bring-up.

The modem startup helper selects `RELATED` subsystem recovery to contain a
modem fault rather than requesting a full SoC reset. This behavior was checked
against the [exact kernel source revision](https://github.com/LineageOS/android_kernel_samsung_sm6115/blob/381a5549ee66fa751f632ee0840f5631274209ee/drivers/soc/qcom/subsystem_restart.c).
The corrected device package installs `/etc/debport/enable-modem` after adding
the alias and readiness checks. Removing that marker disables the modem chain
on the next boot. Do not add it to an uncorrected r1/r2 image manually.

The boot corrections also run `qrtr-ns -f` under systemd, use Debian's
`/usr/bin/btattach`, remove WLAN ordering from NetworkManager and mask the
unused networkd wait-online service. Wi-Fi authentication, regulatory data
and GNOME keyring PAM packages are now explicit runtime dependencies.
The original r1 ZIP requires the graphical startup corrections; r2 contains
those but holds the modem off. The r3 build includes the verified modem/WLAN
startup, Maps and time synchronization. Its device package version is 0.1.2.
Boot and NV-integrity evidence is recorded under `out/modem-bringup/`.
The r3 configuration was tested by upgrading the running r1 root image to
package 0.1.2. The exact fresh r3 filesystem was not flashed; its shared
device configuration passed the physical reboot test.

The r4 build adds the missing ALSA base UCM package, GNOME Camera, compressed
RAM and a Debian Bubblewrap rebuild with its upstream Linux 4.19 fallback
enabled. Device package 0.1.3 declares these dependencies. Speakers reload
automatically after restarting the audio service. The camera gallery,
microphone and video recording were confirmed on the running r1 root image,
now upgraded to 0.1.3. The separate fresh r4 filesystem and installer passed
filesystem, package, systemd and ZIP integrity checks. That fresh image has
not been flashed, and a full reboot after the audio/camera fixes was not tested.
Artifacts and checksums are under `out/debian-gnome-r4/`.

The original port's adaptations are retained or rebuilt as follows:

| Component | Debian integration |
| --- | --- |
| Kernel, DTBs, early firmware | Retained from the verified boot; exact 37 modules |
| Turnip KGSL Vulkan | Mesa 26.2.4 rebuilt against Debian ARM64 libraries |
| Zink OpenGL/EGL/GBM | Mesa 26.0.8 with the port's explicit KGSL device patch |
| GNOME session | Wayland, private Adreno runtime, GTK OpenGL, software fallback |
| GNOME Settings | Debian 48.4 with the private-driver environment fix adapted from the original 51 recipe |
| Touch and rotation | Original GNOME Himax calibration and native Wayland sensor axes |
| Audio | Original UCM routing, Debian base UCM configuration and PulseAudio interrupt scheduling |
| Wi-Fi | Original board-data initializer, matching stock firmware and systemd service |
| Bluetooth | Original Python UART initializer and matching kernel modules |
| Qualcomm firmware services | Rebuilt QRTR, downstream PD mapper and TFTP service |
| DSP and sensors | Rebuilt downstream FastRPC, libssc and patched sensor proxy |
| Modem/GPS | Debian ModemManager 1.24 with the port's GPS unlock and indication-order fixes |
| Camera | Original isolated stock Android HAL, camera broker and rebuilt PipeWire bridge |
| Sandboxed image loading | Debian Bubblewrap 0.12.0 rebuilt with upstream's Linux 4.19 compatibility |
| Memory | Debian zram-tools, LZ4 compressed RAM, maximum 50% of physical RAM |

GNOME, apps and compiled graphics/hardware helpers use Debian's glibc. The
camera keeps its existing isolated Android runtime. APKs are not installed into
Debian. OpenRC startup scripts are translated to systemd units. Modem NV storage
remains read-only. Factory sensor calibration is read locally through debugfs
into a private runtime cache; it is not embedded in the image.

The GNOME image is a separate 6 GiB file. Its installer keeps the working
headless image, the original Linux filesystem and OrangeFox. It updates boot
only after image checksums, filesystem checks and native userspace validation.
The rollback restores the verified headless boot and selects its preserved image.
There is no formatting or repartitioning.

The filesystem is split into eight 768 MiB ZIP entries to stay below the older
recovery's extraction limits. The package verifies the complete reconstructed
image before writing boot. Its boot command line selects `graphical.target`
and reduces console log verbosity.

From r5, GNOME automatically logs into `user`. The local login and sudo password
is `147147`, matching the [official postmarketOS prebuilt image defaults](https://postmarketos.org/download/).
The build renames the prepared desktop account and home to `user` and
`/home/user`, preserving UID/GID 1000, desktop groups and the dedicated SSH key.
GDM and AccountsService select the renamed account and the accelerated GNOME
session. The build verifies the stored password hash against `147147` and
exports `login-defaults.json` and `login-verification.json` with the artifacts.
SSH uses `user@172.16.42.1` with the dedicated key; root remains locked.

The r5 installer contains device package 0.1.4 and retains the r4 audio, camera,
modem and memory corrections. R5 was installed on 19 October 2026 through a
guarded recovery upgrade. The user confirmed the GNOME desktop after reboot.
The upgrade migrated the existing home to `/home/user`, Wi-Fi and Bluetooth
state, machine ID and SSH host keys, and kept a complete verified rollback
image. The new default sudo password was authenticated. Hardware graphics,
Wi-Fi reconnection, speaker/microphone endpoints and compressed RAM were
verified after this boot. `systemd-suspend.service` failed once; suspend is
not claimed as working.

The separate public r5 derivative removes the development SSH authorized key
and all shared machine identity from the pristine, never-booted build tree.
It has offline validation; that exact derivative has not been flashed. The
physical boot test applies to r5 with the tablet's private data migration.
Diagnostics on the installed tablet now select the `user` account. Private
backups, network state and user files are excluded from Git and releases.

Build stages are implemented in `tools/prepare-gnome-userspace.py`,
`fetch-gta4l-sources.py`, `prepare-gnome-compiler.sh`,
`fetch-debian-desktop-sources.sh`, `build-gta4l-debian-components.py`,
`build-bubblewrap-compat.py`,
`integrate-gta4l-gnome.py`, `finalize-gnome-image.py` and
`package-gnome-device.py`. Native Linux build trees are kept under `/var/tmp`;
archives, component receipts, package inventories and logs record inputs.
Original source archives and patches are checksum verified. Debian source
packages are obtained through its signed APT indexes. The compiler environment
is isolated; no Windows or WSL host packages are installed.

The shared declarative Debian base builder remains independent of these
SM-T505-specific preview adaptations.
