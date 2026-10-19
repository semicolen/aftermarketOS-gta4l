"""Assemble Debian-native SM-T505 adaptations and the isolated stock camera HAL."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))
from debport.build import write
from gta4l.account import USERNAME


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    root = args.rootfs.resolve()
    repo = Path(__file__).resolve().parents[1]
    upstream = repo / "upstream/2gta4l"
    if os.geteuid() != 0 or json.loads((root / "etc/debport-image.json").read_text())["device"] != "samsung-gta4l":
        raise ValueError("Linux root and the prepared device rootfs are required")
    if not (root / "usr/bin/gnome-shell").is_file():
        raise ValueError("GNOME userspace is missing")
    if digest(args.runtime) != "a1ec91dcf156aab08aa8dad5b6d8a83a1db81e4300149979cd3edf0bd614afb6":
        raise ValueError("stock runtime export checksum mismatch")
    required = ["turnip", "zink", "qrtr", "pd-mapper", "tqftpserv", "hexagonrpc",
                "libssc", "iio-sensor-proxy", "local-helpers", "modemmanager", "gnome-settings", "bubblewrap"]
    for name in required:
        receipt = args.compiler / "build/receipts" / (name + ".json")
        if not receipt.is_file() or json.loads(receipt.read_text())["status"] != "built":
            raise ValueError("component is not built: " + name)
    stage = root.parent / "device-package"
    stage.mkdir(exist_ok=False)
    for directory in ("usr/lib/debport-device", "usr/lib/gta4l-zink", "usr/lib/gta4l-kgsl", "usr/lib/debport-gnome-settings"):
        shutil.copytree(args.compiler / directory, stage / directory, symlinks=True)
    with tarfile.open(args.runtime) as archive:
        members = []
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("unsafe runtime path")
            if member.name.startswith(("usr/lib/gta4l-camera/", "usr/share/gta4l-sensors/")) or member.name in (
                "usr/lib/gta4l-camera", "usr/share/gta4l-sensors"):
                members.append(member)
        archive.extractall(stage, members=members, filter="data")
    provenance = {}

    def copy(relative, target, executable=False):
        source = upstream / relative
        destination = stage / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if executable else 0o644)
        provenance[target] = {"source": relative, "sha256": digest(source)}

    def link(target, destination):
        path = stage / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)

    device = "port/device-samsung-gta4l/"
    for name in ("98-touchscreen-cal.rules", "79-gta4l-kgsl.rules", "79-gta4l-ion.rules", "78-mm-gta4l.rules"):
        copy(device + name, "etc/udev/rules.d/" + name)
    copy("port/rotation-gta4l/81-gta4l-sensors.rules", "etc/udev/rules.d/81-gta4l-sensors.rules")
    for name in ("82-gta4l-wayland-sensors.rules", "99-gta4l-gnome-touch.rules"):
        copy("ui-profiles/" + name, "etc/udev/rules.d/" + name)
    for name in ("gta4l.conf", "HiFi.conf"):
        copy("port/alsa-ucm-gta4l/" + name, "usr/share/alsa/ucm2/Qualcomm/gta4l/" + name)
    link("../../Qualcomm/gta4l/gta4l.conf", "usr/share/alsa/ucm2/conf.d/bengal-qrd-snd-/bengal-qrd-snd-card.conf")
    copy("port/alsa-ucm-gta4l/90-gta4l-audio.rules", "etc/udev/rules.d/90-gta4l-audio.rules")
    copy("port/alsa-ucm-gta4l/90-gta4l-audio.pa", "etc/pulse/default.pa.d/90-gta4l-audio.pa")
    copy("port/wlfw-gta4l/gta4l-wlan-start", "usr/bin/gta4l-wlan-start", True)
    copy("port/bluetooth-gta4l/gta4l-bt-initialize.py", "usr/bin/gta4l-bt-initialize", True)
    bluetooth = stage / "usr/bin/gta4l-bt-initialize"
    bluetooth.write_text(bluetooth.read_text().replace("/usr/sbin/btattach", "/usr/bin/btattach"))
    copy("port/sensors-gta4l/gta4l-sensors-prepare.py", "usr/bin/gta4l-sensors-prepare", True)
    copy("port/gps-gta4l/gta4l-gps-prepare.py", "usr/libexec/gta4l-gps-prepare", True)
    copy("port/gps-gta4l/gta4l-gps-unlock", "etc/ModemManager/gta4l-gps-unlock")
    copy("port/gps-gta4l/90-gta4l-gps.conf", "etc/geoclue/conf.d/90-gta4l-gps.conf")
    copy("port/gps-assistance-gta4l/gta4l-gps-assistance.py", "usr/libexec/gta4l-gps-assistance.py", True)
    for source, target, mode in (
        ("70-gta4l-rmtfs.rules", "etc/udev/rules.d/70-gta4l-rmtfs.rules", 0o644),
        ("gta4l-rmtfs-ready.py", "usr/libexec/gta4l-rmtfs-ready", 0o755),
        ("gta4l-modem-preflight.py", "usr/libexec/gta4l-modem-prepare", 0o755),
        ("gta4l-modem-ready.py", "usr/libexec/gta4l-modem-ready", 0o755),
    ):
        destination = stage / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / "ports/samsung-gta4l" / source, destination)
        destination.chmod(mode)
    for filename, target in (("gta4l-camera.py", "usr/bin/gta4l-camera"),
                             ("gta4l-camera-service.py", "usr/libexec/gta4l-camera-service.py"),
                             ("gta4l-camera-run", "usr/libexec/gta4l-camera-run"),
                             ("gta4l-camera.desktop", "usr/share/applications/gta4l-camera.desktop")):
        copy("port/camera-gta4l/" + filename, target, not filename.endswith(".desktop"))
    copy("port/camera-pipewire-gta4l/gta4l-camera-pipewire-session.py", "usr/libexec/gta4l-camera-pipewire-session", True)
    copy("port/camera-pipewire-gta4l/gta4l-camera-pipewire.desktop", "etc/xdg/autostart/gta4l-camera-pipewire.desktop")
    copy("port/camera-pipewire-gta4l/60-gta4l-camera.conf", "etc/wireplumber/wireplumber.conf.d/60-gta4l-camera.conf")
    write(stage, "etc/wireplumber/wireplumber.conf.d/61-gta4l-pulse.conf",
          "wireplumber.profiles = { main = { monitor.alsa = disabled monitor.bluez = disabled } }\n")
    prefix = "/usr/lib/debport-device"
    for name in ("wlfw-initialize-gta4l", "gta4l-subsystem"):
        link(prefix + "/bin/" + name, "usr/bin/" + name)
    link(prefix + "/bin/gta4l-camera-pipewire", "usr/libexec/gta4l-camera-pipewire")
    copy("port/mesa-zink-kgsl-gta4l/gta4l-zink-run", "usr/bin/gta4l-zink-run", True)
    copy("ui-profiles/gta4l-gnome-session", "usr/bin/gta4l-gnome-session", True)
    wrapper = stage / "usr/bin/gta4l-gnome-session"
    wrapper.write_text(wrapper.read_text().replace('exec /usr/bin/gnome-session "$@"',
        'dbus-update-activation-environment --systemd GSK_RENDERER LIBGL_ALWAYS_SOFTWARE GALLIUM_DRIVER '
        'GTA4L_ZINK_KGSL MESA_LOADER_DRIVER_OVERRIDE VK_DRIVER_FILES LIBGL_KOPPER_DISABLE '
        'LIBGL_DRIVERS_PATH LD_LIBRARY_PATH 2>/dev/null || true\nexec /usr/bin/gnome-session "$@"'))
    copy("ui-profiles/gnome-rendering-profile.sh", "etc/profile.d/80-gta4l-rendering.sh")
    write(stage, "usr/share/gta4l-kgsl/freedreno_icd.aarch64.json", json.dumps({
        "file_format_version": "1.0.0", "ICD": {"library_path": "/usr/lib/gta4l-kgsl/libvulkan_freedreno.so", "api_version": "1.4.0"}}, indent=2) + "\n")
    session = "[Desktop Entry]\nName=Debian GNOME\nComment=SM-T505 Adreno session\nType=Application\nDesktopNames=GNOME\nExec=/usr/bin/gta4l-zink-run /usr/bin/gta4l-gnome-session --session=gnome\n"
    write(stage, "usr/share/wayland-sessions/debport-gnome.desktop", session)
    write(stage, "usr/share/wayland-sessions/debport-gnome-software.desktop", session.replace(
        "Name=Debian GNOME", "Name=Debian GNOME (Software)").replace("/usr/bin/gta4l-zink-run ", ""))
    write(stage, "var/lib/AccountsService/users/" + USERNAME, "[User]\nSession=debport-gnome\nXSession=debport-gnome\nSystemAccount=false\n")
    write(stage, "etc/environment.d/80-gta4l-rendering.conf", "LIBGL_ALWAYS_SOFTWARE=1\nGALLIUM_DRIVER=llvmpipe\nGSK_RENDERER=gl\n")
    modules = sorted(path.stem for path in (root / "usr/lib/modules/4.19.300-perf").rglob("*.ko")
                     if "/techpack/audio/" in str(path) or "/qcacld-3.0/" in str(path))
    if "machine_dlkm" not in modules or "wlan" not in modules:
        raise ValueError("matching audio/WLAN modules are missing")
    write(stage, "etc/modules-load.d/gta4l.conf", "\n".join(modules + ["bnep", "hidp", "rmnet_perf", "rmnet_shs"]) + "\n")
    units = []

    def unit(name, description, command, needs="", after="", oneshot=False, environment=(), extra="", install=True, kind="simple"):
        text = "[Unit]\nDescription=" + description + "\nAfter=systemd-udev-trigger.service " + after + "\n"
        if needs:
            text += "Requires=" + needs + "\nAfter=" + needs + "\n"
        text += "[Service]\nType=" + ("oneshot" if oneshot else kind) + "\n"
        text += "Environment=LD_LIBRARY_PATH=" + prefix + "/lib\nEnvironment=PATH=" + prefix + "/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
        for value in environment:
            text += "Environment=" + value + "\n"
        text += "ExecStart=" + command + "\n" + ("RemainAfterExit=yes\n" if oneshot else "Restart=on-failure\nRestartSec=10\n")
        text += extra
        if install:
            text += "[Install]\nWantedBy=multi-user.target\n"
            units.append(name)
        write(stage, "etc/systemd/system/" + name, text)

    unit("gta4l-qrtr.service", "SM-T505 QRTR name server", prefix + "/bin/qrtr-ns -f", after="systemd-modules-load.service")
    qrtr = "gta4l-qrtr.service"
    unit("gta4l-pd-mapper.service", "SM-T505 downstream protection-domain mapper", prefix + "/bin/pd-mapper", qrtr,
         environment=["PD_MAPPER_FW_DIR=/lib/firmware/postmarketos"])
    unit("gta4l-tqftpserv.service", "SM-T505 downstream firmware server", prefix + "/bin/tqftpserv", qrtr,
         environment=["TQFTPSERV_FW_DIR=/lib/firmware/postmarketos"])
    firmware = "gta4l-qrtr.service gta4l-pd-mapper.service gta4l-tqftpserv.service"
    unit("gta4l-rmtfs.service", "SM-T505 read-only modem NV storage", "/usr/bin/rmtfs -P -r", qrtr, kind="exec",
         extra="ExecStartPre=/usr/bin/udevadm settle --timeout=10\nExecStartPre=/usr/libexec/gta4l-rmtfs-ready\nExecStartPost=/usr/libexec/gta4l-rmtfs-ready --wait $MAINPID\nTimeoutStartSec=45\nKillSignal=SIGINT\n")
    unit("gta4l-adsp.service", "SM-T505 audio and sensor DSP", prefix + "/bin/gta4l-subsystem /dev/subsys_adsp", firmware)
    unit("gta4l-modem.service", "SM-T505 LTE modem subsystem", prefix + "/bin/gta4l-subsystem /dev/subsys_modem", firmware + " gta4l-rmtfs.service", kind="exec",
         extra="ExecStartPre=/usr/libexec/gta4l-modem-prepare\nExecStartPost=/usr/libexec/gta4l-modem-ready\nTimeoutStartSec=60\n")
    write(stage, "usr/libexec/gta4l-ipa-start", "#!/bin/sh\nset -eu\n[ -c /dev/ipa ]\nprintf '1\\n' > /dev/ipa\nfor n in $(seq 1 15); do [ ! -e /sys/class/net/rmnet_ipa0 ] || exit 0; sleep 1; done\nexit 1\n")
    (stage / "usr/libexec/gta4l-ipa-start").chmod(0o755)
    unit("gta4l-ipa.service", "SM-T505 signed IPA firmware", "/usr/libexec/gta4l-ipa-start", "gta4l-modem.service", oneshot=True)
    unit("gta4l-wlan.service", "SM-T505 WLAN board-data initialization", "/usr/bin/gta4l-wlan-start",
         "gta4l-modem.service", after="systemd-modules-load.service gta4l-ipa.service", oneshot=True, extra="TimeoutStartSec=120\n")
    unit("gta4l-bluetooth.service", "SM-T505 stock Bluetooth UART initialization", "/usr/bin/gta4l-bt-initialize",
         after="systemd-modules-load.service")
    write(stage, "etc/systemd/system/bluetooth.service.d/10-gta4l.conf", "[Unit]\nWants=gta4l-bluetooth.service\nAfter=gta4l-bluetooth.service\n")
    unit("gta4l-sensors.service", "SM-T505 private read-only sensor registry server",
         prefix + "/bin/hexagonrpcd -s -f /dev/adsprpc-smd-secure -R /var/lib/gta4l-sensors/runtime",
         firmware + " gta4l-adsp.service", extra="ExecStartPre=/usr/bin/gta4l-sensors-prepare\n")
    unit("iio-sensor-proxy.service", "SM-T505 patched Qualcomm SSC sensor proxy", prefix + "/libexec/iio-sensor-proxy",
         "gta4l-sensors.service", extra="BusName=net.hadess.SensorProxy\n")
    for relative in ("share/dbus-1/system.d/net.hadess.SensorProxy.conf", "lib/udev/rules.d/80-iio-sensor-proxy.rules"):
        target = stage / "etc" / (relative.removeprefix("share/").removeprefix("lib/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stage / prefix.lstrip("/") / relative, target)
    unit("gta4l-camera.service", "SM-T505 on-demand stock camera controller", "/usr/bin/python3 /usr/libexec/gta4l-camera-service.py")
    modem_executable = prefix + "/sbin/ModemManager"
    unit("ModemManager.service", "SM-T505 ModemManager with GPS request fixes", modem_executable,
         "gta4l-modem.service", after="dbus.service gta4l-ipa.service")
    unit("gta4l-gps-assistance.service", "SM-T505 client-controlled GNSS assistance", "/usr/bin/python3 /usr/libexec/gta4l-gps-assistance.py",
         "ModemManager.service", after="dbus.service")
    # Native units replace the generic mainline-only daemons installed by APT.
    for name in ("qrtr-ns.service", "rmtfs.service", "tqftpserv.service", "systemd-networkd-wait-online.service"):
        link("/dev/null", "etc/systemd/system/" + name)
    # The alias, RMTFS readiness and scoped SSR fixes have passed device bring-up.
    # Retain the opt-in guard so disabling modem startup remains one file change.
    for name in ("gta4l-modem", "gta4l-rmtfs", "gta4l-ipa", "gta4l-wlan",
                 "ModemManager", "gta4l-gps-assistance"):
        write(stage, "etc/systemd/system/" + name + ".service.d/20-modem-preview.conf",
              "[Unit]\nConditionPathExists=/etc/debport/enable-modem\n")
    write(stage, "etc/debport/enable-modem", "Read-only RMTFS, UIO alias and readiness checks enabled.\n")
    write(stage, "etc/systemd/system/NetworkManager.service.d/10-gta4l.conf", "[Unit]\nWants=gta4l-wlan.service\n")
    for name in units:
        link("/etc/systemd/system/" + name, "etc/systemd/system/multi-user.target.wants/" + name)
    write(stage, "usr/bin/gnome-control-center", "#!/bin/sh\nexec /usr/lib/debport-gnome-settings/bin/gnome-control-center \"$@\"\n")
    (stage / "usr/bin/gnome-control-center").chmod(0o755)
    write(stage, "DEBIAN/control", "Package: debport-gta4l-gnome\nVersion: 0.1.4\nArchitecture: arm64\nMaintainer: debport local build\nDescription: Debian SM-T505 downstream device adaptations and GNOME session\nDepends: gdm3, gnome-shell, network-manager, wpasupplicant, wireless-regdb, libpam-gnome-keyring, bluez, pulseaudio, alsa-utils, alsa-ucm-conf, python3-gi, python3-dbus, e2fsprogs, rmtfs, pipewire, wireplumber, libprotobuf-c1, gnome-maps, systemd-timesyncd, libqmi-utils, gnome-snapshot, zram-tools, bubblewrap (>= 0.12.0-1~deb13u1+debport1)\n")
    write(stage, "DEBIAN/preinst", "#!/bin/sh\nset -e\ndpkg-divert --package debport-gta4l-gnome --add --rename --divert /usr/bin/gnome-control-center.debian /usr/bin/gnome-control-center\n")
    (stage / "DEBIAN/preinst").chmod(0o755)
    write(stage, "usr/share/debport/downstream-components.json", json.dumps({"desktop": "GNOME Wayland", "components": required,
          "ported_overlays": provenance, "runtime_export_sha256": digest(args.runtime), "hardware_tested": False}, indent=2) + "\n")
    package = root.parent / "debport-gta4l-gnome_0.1.4_arm64.deb"
    subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(stage), str(package)], check=True)
    print(json.dumps({"package": str(package), "sha256": digest(package), "components": required}, indent=2))


if __name__ == "__main__":
    main()
