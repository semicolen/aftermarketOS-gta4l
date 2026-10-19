# aftermarketOS for gta4l

Debian 13 with GNOME 48 for **Samsung Galaxy Tab A7 LTE SM-T505 / gta4l**,
using downstream Linux `4.19.300-perf #11-postmarketOS` and the adaptations from
[semicolen/2gta4l](https://github.com/semicolen/2gta4l).
The shared Debian bootstrap/backend lives in [aftermarketOS](https://github.com/semicolen/aftermarketOS).

The r5 configuration booted on the physical tablet on 19 October 2026 after
a data-preserving upgrade. The user confirmed the GNOME desktop. USB SSH,
`user` login and sudo, native Turnip/Zink graphics, Wi-Fi auto-reconnection,
speaker/microphone endpoints, modem services and compressed RAM were verified
after boot. Touch, rotation, Bluetooth, Maps GPS, speaker playback and GNOME
Camera photos/gallery/microphone/video were confirmed during the preceding
bring-up with the same hardware adaptations.

**Local login and sudo: `user` / `147147`**, matching the
[postmarketOS prebuilt defaults](https://postmarketos.org/download/).
GNOME auto-login is enabled. Root is locked. Public builds contain no developer
SSH authorized key; install your own key locally to enable SSH access.

## Downloads and installation scope

Builds, firmware/runtime archives, package inventories, checksums and build
receipts are attached to [releases](https://github.com/semicolen/aftermarketOS-gta4l/releases).
Large generated files belong in releases rather than Git history.

This is a device preview. The current OrangeFox ZIP expects the **existing
verified headless Debian/Nura filesystem layout**, exact boot/recovery hashes,
and SM-T505 partition mapping. It does not install onto stock Android or set up
partitions. It refuses an existing GNOME image. Read the release notes before
flashing; they describe the precise prerequisites and validation limits.

The installed test tablet was upgraded separately, preserving its home,
Wi-Fi, Bluetooth and SSH identity with a verified complete backup. Those private
files and backups are not part of any public download. The public r5 derivative
has the development SSH access removed; that exact derivative has offline
validation, while the r5 base with migrated data has the physical boot test.

## Known gaps

- Suspend failed once after the r5 boot; deep sleep/resume is unresolved.
- Cellular data/registration, headset routing and Bluetooth audio are untested
  on Debian. The modem runs with read-only physical NV storage.
- The standard PipeWire camera stream is 640x480. Long recording stability
  and full-resolution third-party camera integration need more testing.
- USB can disconnect intermittently. The GPU uses private KGSL Turnip/Zink;
  the GNOME session forces GTK OpenGL. General native Vulkan presentation is
  not established.

See [GNOME integration](docs/gnome-device-preview.md),
[audio/camera fixes](docs/audio-camera-debug.md), [build instructions](docs/build.md)
and [source/firmware provenance](docs/provenance.md).

## Source layout

```sh
git clone --recurse-submodules https://github.com/semicolen/aftermarketOS-gta4l
cd aftermarketOS-gta4l
python3 builder/tools/verify-rootfs.py --help
PYTHONPATH=builder python3 -m debport plan profiles/samsung-gta4l.json
PYTHONPATH=builder python3 -m unittest discover -s tests -v
```

- `builder/`: pinned shared backend submodule.
- `upstream/2gta4l/`: pinned original port, kernel recipes, patches and helpers.
- `profiles/`, `boot/`, `recovery/`, `ports/`: device metadata and adaptations.
- `tools/`: glibc component builds, GNOME packaging, recovery and diagnostics.
- `gta4l/`: desktop account policy.
- `releases/`: public metadata and installation notes; binaries are release assets.

Historical `build-gnome-r2.sh` through `r5.sh` record the incremental local
bring-up and expect previous work directories. They are not clean-host entry
points. The documented staged build exposes the required inputs explicitly.
