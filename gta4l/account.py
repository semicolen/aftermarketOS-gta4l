"""Local login policy for the GNOME device images."""
import ctypes
import hashlib

from debport.build import write

USERNAME = "user"
PASSWORD = "147147"
DEFAULTS_SOURCE = "https://postmarketos.org/download/"
DESKTOP_GROUPS = ("sudo", "video", "audio", "render", "netdev", "bluetooth")


def entries(root, name):
    return {fields[0]: fields for line in (root / "etc" / name).read_text().splitlines()
            if line and not line.startswith("#") and (fields := line.split(":"))}


def configure(root, chroot):
    accounts = entries(root, "passwd")
    previous_home = "home/user" if USERNAME in accounts else "home/debian"
    key_before = (root / previous_home / ".ssh/authorized_keys").read_bytes()
    if USERNAME not in accounts:
        previous = accounts.get("debian")
        if not previous or previous[2:4] != ["1000", "1000"]:
            raise ValueError("expected the prepared UID/GID 1000 desktop account")
        if (root / "home/user").exists() or (root / "home/user").is_symlink():
            raise ValueError("refusing to replace an existing user home")
        chroot("usermod", "--login", USERNAME, "--home", "/home/user", "--move-home", "debian")
    groups = entries(root, "group")
    if USERNAME not in groups:
        if groups.get("debian", [None, None, None])[2] != "1000":
            raise ValueError("expected the prepared desktop primary group")
        chroot("groupmod", "--new-name", USERNAME, "debian")
    chroot("usermod", "--comment", "User", "--append", "--groups", ",".join(DESKTOP_GROUPS), USERNAME)
    # Pass the password through stdin, outside command lines and build logs.
    chroot("chpasswd", input=f"{USERNAME}:{PASSWORD}\n", text=True)
    write(root, "etc/gdm3/daemon.conf", (
        f"[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin={USERNAME}\n"
        "[security]\n[xdmcp]\n[chooser]\n[debug]\n"
    ))
    write(root, "etc/motd", f"Debian GNOME SM-T505 preview. USB SSH: {USERNAME}@172.16.42.1\n")
    write(root, "etc/issue", f"Debian 13 GNOME SM-T505 - USB SSH: {USERNAME}@172.16.42.1\n")
    if (root / "home/user/.ssh/authorized_keys").read_bytes() != key_before:
        raise ValueError("the account rename changed the dedicated SSH key")


def verify(root):
    accounts = entries(root, "passwd")
    account = accounts.get(USERNAME)
    if "debian" in accounts or not account or account[2:4] != ["1000", "1000"] or account[5:] != ["/home/user", "/bin/bash"]:
        raise ValueError("desktop account rename or home configuration is incomplete")
    groups = entries(root, "group")
    if groups.get(USERNAME, [None, None, None])[2] != "1000" or any(
        USERNAME not in groups.get(name, ["", "", "", ""])[3].split(",") for name in DESKTOP_GROUPS
    ):
        raise ValueError("desktop account group membership is incomplete")
    shadow = entries(root, "shadow")
    encoded = shadow[USERNAME][1].encode()
    crypt = ctypes.CDLL("libcrypt.so.1").crypt
    crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    crypt.restype = ctypes.c_char_p
    if crypt(PASSWORD.encode(), encoded) != encoded:
        raise ValueError("the default local password did not verify")
    if not shadow["root"][1].startswith(("!", "*")):
        raise ValueError("root must remain locked")
    home = root / "home/user"
    key = home / ".ssh/authorized_keys"
    if not key.is_file() or key.stat().st_uid != 1000 or key.stat().st_mode & 0o777 != 0o600:
        raise ValueError("the dedicated SSH key was not preserved")
    if home.stat().st_uid != 1000 or (home / ".ssh").stat().st_mode & 0o777 != 0o700:
        raise ValueError("desktop home ownership or SSH directory permissions are incorrect")
    if "AutomaticLogin=user\n" not in (root / "etc/gdm3/daemon.conf").read_text():
        raise ValueError("GDM must select the renamed user")
    session = root / "var/lib/AccountsService/users/user"
    if "Session=debport-gnome\n" not in session.read_text():
        raise ValueError("the hardware-accelerated GNOME session is not selected")
    return {"username": USERNAME, "uid": 1000, "gid": 1000,
            "password_hash_verified": True, "desktop_groups_verified": True,
            "home_and_ssh_permissions_verified": True, "gdm_auto_login": USERNAME,
            "root_locked": True, "authorized_key_sha256": hashlib.sha256(key.read_bytes()).hexdigest(),
            "defaults_source": DEFAULTS_SOURCE}
