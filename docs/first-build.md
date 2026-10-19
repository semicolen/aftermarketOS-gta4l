# First Debian ARM64 base build — 2026-10-18

The reusable backend built Debian 13 (`trixie`) ARM64 using the
`samsung-gta4l` profile. This is a **base root filesystem**, not a bootable
SM-T505 image or recovery installer. No tablet partitions were written.

## Artifacts

Saved in `out/debport-gta4l-20261018/`:

| File | Size / purpose |
| --- | --- |
| `rootfs.ext4` | 2 GiB sparse filesystem image |
| `rootfs.tar.xz` | 62,067,924 bytes; compressed root filesystem |
| `packages.tsv` | Exact versions and architectures of 126 installed packages |
| `manifest.json` | Profile/source metadata, build state, hashes and host tool paths |
| `SHA256SUMS` | Export integrity checks |
| `verification.json` | Passed artifact and emulated-userspace checks |

The unpacked Linux tree and locally extracted bootstrap tools remain under
`/var/tmp/debport-gta4l-20261018/` in WSL Ubuntu. No host packages were installed.
Debian archive signatures were verified, and security/updates repositories
were refreshed before packaging.

## Validation performed

- Six profile/import tests passed on Windows and WSL Linux. These include
  rejecting shell commands/substitutions and comparing the real upstream
  deviceinfo's boot parameters with the bundled SM-T505 profile.
- ARM64 ELF machine ID 183 and `dpkg --print-architecture` agree.
- `dpkg --audit` reports no unconfigured packages.
- systemd `257.13-1~deb13u1` executes under QEMU userspace emulation.
- The tar archive can be read and contains the expected system and identity files.
- Read-only `e2fsck` passes all five stages on the ext4 file.
- The image's identity file identifies the correct rootfs-only profile.
- Machine ID and SSH host keys are absent for first-boot generation. Root
  password is locked and SSH is masked; this build has no supplied login key.
- All four exported artifacts in `SHA256SUMS` were rehashed on Windows and match.

These checks use the WSL host kernel. They do not start Debian systemd as PID 1,
test Linux 4.19 compatibility, or establish any physical-device functionality.
There is no device kernel, firmware, accelerated desktop, initramfs, Android
boot image or installer in these artifacts.

## Image hashes

```text
c49efd5ed3b85e2378d4ef6bb240f49bcdb1c950fa8e9fb8bcf6f4883bb5299e  rootfs.ext4
9c003bbd26169c9d18e2da302c049d3cfebb602c50061c2e1bf25528f277a04d  rootfs.tar.xz
```

The next device milestone is a packaged kernel/DTB/module set and a Debian
initramfs that can reach a diagnostic console on the tablet. Hardware services
and the glibc graphics rebuild follow that boot milestone.
