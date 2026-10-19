# Audio and GNOME Camera corrections

On 19 October 2026, the SM-T505 user confirmed speaker playback, microphone
capture, saved photographs in GNOME Camera's gallery, and video recording.
The app tested was Debian's `gnome-snapshot` 48.0.1-1. These checks were made
on the running GNOME image with the corrections installed through APT/dpkg.

## Audio

The original port's device-specific UCM files were present, but the Debian
`alsa-ucm-conf` package was missing. Without its top-level
`/usr/share/alsa/ucm2/ucm.conf`, ALSA could not resolve the custom profile.
PulseAudio failed to load the real card and offered Dummy Output instead.

Installing `alsa-ucm-conf` fixed `alsaucm -c hw:0 list _verbs` and enabled the
original port's explicit, interrupt-scheduled PulseAudio card module. The
user heard a short speaker test. Restarting `pulseaudio.service` then loaded
the speaker and microphone endpoints automatically. The dependency is now
declared both in the GNOME userspace stage and the device package.

## Camera

Capture had already saved valid 640×480 JPEG files, but Snapshot could not
load them into its gallery. Files were decoded locally for validation; no
photographs were exported or inspected visually.

The failing loader used Bubblewrap. A minimal sandbox running `/usr/bin/true`
reproduced the error without accessing a photograph:

```text
bwrap: Can't open source /usr: Function not implemented
openat2(..., RESOLVE_NO_MAGICLINKS|RESOLVE_IN_ROOT, ...) = -1 ENOSYS
```

Debian's `bubblewrap` 0.12.0-1~deb13u1 is built with
`-Dassume_kernel=5.10.0`. The tablet uses 4.19.300. Upstream 0.12.0 includes
an older-kernel path-resolution fallback, but the Debian build compiles it
out. See the [upstream release notes](https://github.com/containers/bubblewrap/releases/tag/v0.12.0).

`tools/build-bubblewrap-compat.py` rebuilds that same Debian source with
`-Dassume_kernel=4.19.0`, producing
`bubblewrap_0.12.0-1~deb13u1+debport1_arm64.deb`. It retains the current
path-resolution security fixes, namespaces and Glycin's seccomp filter.
The sandbox smoke test then returned zero; restarting Snapshot restored the
gallery, and the user confirmed photographs, microphone audio and video.
Cross-build tests are recorded as skipped; the sandbox was tested on the
physical tablet instead.

The compatibility package is a normal dpkg-managed rebuild. When updating
Bubblewrap, repeat this configuration change and device test for the new
source version; standard Debian builds may assume a newer kernel again.

## Memory and artifacts

GNOME Maps had previously used approximately 1 GiB of the tablet's available
2.7 GiB, leaving only about 127 MiB available with no swap. Glycin also limits
its loader's address space according to available RAM and swap. Debian's
`zram-tools` now enables an LZ4 compressed-RAM swap device with a maximum
size of 50% of RAM (about 1.3 GiB). It passed native startup and is enabled
for future boots. It does not use tablet storage for swap.

The revised device package is 0.1.3. `tools/build-gnome-r4.sh` creates the r4
OrangeFox installer from the previous rootfs with `alsa-ucm-conf`, Snapshot,
zram-tools and the rebuilt Bubblewrap. Package inventories and checksums
are retained with the artifacts. Building the installer does not flash it.

Runtime diagnostic evidence is under `out/audio-camera-debug/`. Earlier
boot, modem and GPS verification remains under `out/modem-bringup/`.
Headset routing, Bluetooth audio and long-duration video recording have not
been verified by these tests.
