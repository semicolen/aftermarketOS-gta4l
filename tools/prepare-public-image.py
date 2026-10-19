"""Copy a pristine r5 build, remove development access and create a public image.

This accepts the never-booted build tree, never a mounted/live device root.
Unexpected home or network state is refused, not silently redistributed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Linux root is required to preserve image ownership')
    source = args.prepared.resolve()
    output = args.output.resolve()
    if output.exists() or str(output).startswith(str(source) + '/') or source == output:
        raise ValueError('output must be a new directory outside the prepared tree')
    if not str(output).startswith(('/var/tmp/', '/home/')):
        raise ValueError('use native Linux storage under /var/tmp or /home')
    manifest = json.loads((source / 'rootfs-manifest.json').read_text())
    root = source / 'rootfs'
    identity = json.loads((root / 'etc/debport-image.json').read_text())
    if identity.get('username') != 'user' or manifest['device_package'] != 'debport-gta4l-gnome_0.1.4_arm64.deb':
        raise ValueError('expected the verified r5 account and device package')
    allowed = {'.bashrc', '.profile', '.bash_logout', '.ssh/authorized_keys'}
    actual = {str(p.relative_to(root / 'home/user')) for p in (root / 'home/user').rglob('*') if p.is_file() or p.is_symlink()}
    if not actual <= allowed or {p.name for p in (root / 'home').iterdir()} != {'user'}:
        raise ValueError('unexpected home contents; only the pristine build is accepted')
    for directory in ('etc/NetworkManager/system-connections', 'var/lib/bluetooth',
                      'usr/lib/gta4l-camera/runtime/data', 'var/cache/gta4l-sensors'):
        if any(p.is_file() or p.is_symlink() for p in (root / directory).rglob('*')):
            raise ValueError('unexpected personal/network/runtime state: ' + directory)
    if (root / 'etc/machine-id').exists() or list((root / 'etc/ssh').glob('ssh_host_*')):
        raise ValueError('a booted identity was found')
    if list((root / 'root').rglob('authorized_keys')) or list((root / 'root').rglob('id_*')):
        raise ValueError('unexpected root SSH access')
    output.mkdir(parents=True)
    subprocess.run(['cp', '-a', str(root), str(output / 'rootfs')], check=True)
    public = output / 'rootfs'
    (public / 'home/user/.ssh/authorized_keys').unlink(missing_ok=True)
    if list(public.rglob('authorized_keys')):
        raise ValueError('an authorized key remains in the copied tree')
    for name in ('var/lib/systemd/random-seed', 'var/lib/dbus/machine-id'):
        (public / name).unlink(missing_ok=True)
    for p in (public / 'var/log').rglob('*'):
        if p.is_file() and not p.is_symlink():
            p.write_bytes(b'')
    identity['ssh'] = 'key-only-no-authorized-keys'
    identity['distribution'] = 'r5-public'
    (public / 'etc/debport-image.json').write_text(json.dumps(identity, indent=2) + '\n')
    (public / 'etc/motd').write_text('aftermarketOS Debian GNOME SM-T505 preview. Local login: user\nInstall your own SSH public key before using USB SSH.\n')
    subprocess.run(['chroot', str(public), 'dpkg', '--audit'], check=True)
    subprocess.run(['chroot', str(public), 'gnome-shell', '--version'], check=True)
    subprocess.run(['chroot', str(public), 'bwrap', '--version'], check=True)
    units = [p.name for p in (public / 'etc/systemd/system').glob('gta4l-*.service')]
    subprocess.run(['chroot', str(public), 'systemd-analyze', '--man=no', 'verify', *units, 'gdm3.service', 'ssh.service'], check=True)
    image = output / 'rootfs.ext4'
    with image.open('xb') as stream:
        stream.truncate(6 * 1024**3)
    subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-F', '-b', '4096', '-L', 'debport-gnome',
                    '-U', str(uuid.uuid4()), '-O', '^orphan_file,^metadata_csum_seed', '-d', str(public), str(image)], check=True)
    subprocess.run(['e2fsck', '-f', '-n', str(image)], check=True)
    manifest.update(image_sha256=sha(image), identity=identity, device_boot_tested=False,
                    public_derivative_of='r5', development_ssh_access_removed=True)
    manifest['login_verification'].pop('authorized_key_sha256', None)
    manifest['login_verification']['home_and_ssh_permissions_verified'] = True
    manifest['login_verification']['authorized_keys_present'] = False
    (output / 'rootfs-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for name in ('packages-final.tsv', 'login-defaults.json', 'bubblewrap_0.12.0-1~deb13u1+debport1_arm64.deb',
                 'debport-gta4l-gnome_0.1.4_arm64.deb'):
        shutil.copyfile(source / name, output / name)
    print(json.dumps({'public_image': str(image), 'sha256': manifest['image_sha256'],
                      'development_ssh_access_removed': True, 'personal_state_checks': 'passed'}))


if __name__ == '__main__':
    main()
