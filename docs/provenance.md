# Source and firmware provenance

The pinned original port is `semicolen/2gta4l` revision
`ea1134e326e667d7c575670766dd9b9b5fd0077c` in the `upstream/2gta4l`
submodule. The shared builder is pinned in `builder`. Debian GNOME is rebuilt
against glibc; Alpine APKs are not installed into Debian.

| Component | Source |
| --- | --- |
| Linux 4.19.300, modules, DTBs | [LineageOS kernel revision 381a5549](https://github.com/LineageOS/android_kernel_samsung_sm6115/tree/381a5549ee66fa751f632ee0840f5631274209ee), with the pinned port's `port/linux-samsung-gta4l/` recipe, config and patches |
| Turnip | Mesa 26.2.4, KGSL backend |
| Zink | Mesa 26.0.8 with explicit KGSL device patch |
| QRTR, PD mapper, TFTP, FastRPC, libssc, sensor proxy | Source versions, URLs and SHA512 values in `releases/r5/component-sources.json`; patches/recipes in the original-port submodule |
| ModemManager | Debian 1.24.0 with `ports/samsung-gta4l/patches/debian-modemmanager-1.24-gps.patch` |
| GNOME Settings | Debian 48.4 with the Debian renderer patch |
| Bubblewrap | Debian 0.12.0-1~deb13u1, rebuilt as +debport1 with upstream's Linux 4.19 fallback enabled |
| Radio, Wi-Fi, touchscreen, camera HAL and sensor DSP runtime | SM-T505 stock T505XXS8CXG1 exports, as described by the original port's firmware/camera recipes |

The release source bundle contains the verified component archives, original
Debian source descriptors/tarballs, patched Debian sources and original port
patches/config. Kernel source is supplied separately. Debian package versions
are recorded in `packages-final.tsv`. Debian packages retain their copyright
and license files under `/usr/share/doc` in the image; their source packages
are available through Debian source repositories.

Firmware/runtime blobs are proprietary Samsung/Qualcomm components; their
original terms apply. The repository license covers original integration code
only. It does not relicense stock firmware or third-party code. Kernel GPL,
Mesa MIT, helper BSD/MIT, and GPL/LGPL component terms remain in force; source
archives include their upstream notices.

The hardware and desktop runtime exports are narrowly selected code/firmware
paths. They exclude `/persist`, personal factory calibration, modemst1/2, fsg,
fsc, account state, saved Wi-Fi/Bluetooth profiles and user media. The public
image is derived from the never-booted build tree, and contains no development
authorized key, SSH host keys or shared machine ID. The flashed tablet's private
data migration and raw backups stay local.
