# SM-T505 Debian boot test

This is an experimental **command-line / USB SSH** image. There is no graphical
desktop and normal tablet hardware integration is incomplete. The shared base
builder remains separate from this device-specific test packager.

**Installation status:** revision 4 passed its first boot on the SM-T505.
Dedicated-key SSH over USB RNDIS reports Debian 13.7, kernel
`4.19.300-perf #11-postmarketOS`, systemd `running`, and zero failed services.
The tablet has returned to OrangeFox for the [GNOME preview](gnome-device-preview.md).

The first sideload was interrupted by a spontaneous recovery restart. With
explicit user approval, journal replay and a full filesystem repair completed.
Safe automatic checking required a manual orphan-list decision: inode 16 had
zero links, zero size and no data blocks. Only that repair prompt was accepted,
and a fresh full read-only check passed. Undo logs are saved under
`out/debian-device-test-r3/`. The two verified failed-attempt files were removed.

Installing from a ZIP in recovery RAM then extracted and checksum-verified
the image successfully. OrangeFox's loop utility rejected its long path;
revision 4 uses shorter mount paths and resumed from the exact verified image.
The resume mode checks both existing files and their hashes before continuing.

## What the installer does

- Requires SM-T505 recovery, the backed-up boot/recovery hashes, the observed
  userdata size and the exact existing nested partition table.
- Checks the existing Linux filesystem with a modern read-only `e2fsck` copied
  from its verified boot image. OrangeFox's built-in 1.45.4 checker cannot read
  the existing filesystem's newer compatibility feature.
- Adds `/var/lib/debport/debian-test-20261018.ext4` and an exact original boot
  backup inside the existing Linux filesystem. It refuses to overwrite an
  existing debport directory. There is no formatting or repartitioning.
- Tests mounting the Debian file and executing its ARM64 systemd binary in
  recovery before updating boot.
- Updates only the raw boot partition, keeping its kernel, DTBs and early
  firmware. The initramfs's second stage is changed to mount the separate
  Debian file and start Debian systemd.
- Verifies the entire boot partition's expected final hash and the unchanged
  recovery hash. It does not reboot automatically.

## Inputs and tests

The existing kernel is `4.19.300-perf #11-postmarketOS`. Its 37 matching modules
and installed firmware were exported through a read-only, no-journal-replay
mount. Boot and recovery were backed up locally and compared with on-device
SHA256 values before packaging.

The Debian base's shell, glibc 2.41, `dpkg` and systemd 257 version command also
executed natively in recovery RAM on the device's stock recovery kernel
`4.19.157-perf`. This is userspace validation, not a Debian PID 1 boot test.

Fourteen tests cover metadata import, boot-image parsing/repacking, unchanged
kernel/DTB/firmware data, and rejection of a wrong device, changed boot or
changed partition table before any write. Image consistency and systemd unit
verification also pass.

The device-test filesystem is **1.5 GiB**. Recovery aborted while extracting
the earlier 2 GiB ZIP entry; the smaller entry passes native streamed extraction
and matches the host checksum. The original 2 GiB base image remains separate.

## Artifacts and first boot

The installed build is under `out/debian-device-test-r4/`, including the ZIP,
`manifest.json`, installation/verification logs, and its exact boot rollback
ZIP. Revision 3's logs retain the earlier interruption and recovery history.
`installation-status.json` records installation and the successful first boot
separately. Its original firmware/kernel tests are not full hardware validation.

The internal `DEBPORT_RESUME_VERIFIED_IMAGE=1` mode requires exactly the original
boot backup and final Debian image, with matching types, size and checksums.
Normal installation still refuses an existing debport directory.

After reboot, USB networking should expose `172.16.42.1`, with the host offered
`172.16.42.2`. SSH uses the `debian` account and the dedicated local key:

```powershell
ssh -i '.cache/keys/debport-test' -o IdentitiesOnly=yes -o UserKnownHostsFile='.cache/keys/debport-known-hosts' -o StrictHostKeyChecking=accept-new debian@172.16.42.1
```

There is no shared password; password authentication and root SSH are disabled.
The private key stays in the ignored `.cache/keys/` directory on the host.
The account can read journals through its `adm`/`systemd-journal` membership.

Useful first-boot checks are `cat /etc/os-release`, `uname -a`,
`systemctl --failed`, `findmnt /`, and `journalctl -b`. Initramfs logs are
preserved at `/run/debport-initramfs.log` and `/run/debport-pre-handoff.log`.
The separate image stores Debian journals persistently.

## Rollback

`SM-T505-restore-previous-boot.zip` restores and verifies the complete original
boot partition after checking that the installed boot is the expected test
image. Use it from OrangeFox if the Debian boot test fails. It leaves the
separate Debian file on disk and makes the original Linux installation boot
again. Complete local boot and recovery backups remain under
`out/recovery-backup-20261018/`.

Do not sideload the generic base `.ext4` or tarball. The generated, guarded
OrangeFox ZIP is the installation artifact.
