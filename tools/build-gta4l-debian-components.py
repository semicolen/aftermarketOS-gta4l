"""Cross-build the pinned SM-T505 graphics and hardware adaptations for glibc."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


def sha(path, algorithm="sha512"):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    root = args.builder.resolve()
    if not (root / "build/compiler-ready").is_file():
        raise ValueError("compiler environment is not ready")
    repo = Path(__file__).resolve().parents[1]
    upstream = repo / "upstream/2gta4l/port"
    work = root / "build"
    receipts = work / "receipts"
    receipts.mkdir(exist_ok=True)
    manifest = json.loads((args.sources / "sources.json").read_text())
    sources = {item["package"]: item for item in manifest["sources"]}
    prefix = "/usr/lib/debport-device"
    current = None

    def run(*command, cwd=None, env=None):
        argv = ["chroot", str(root)]
        argv += ["/usr/bin/env", "PKG_CONFIG_PATH=" + prefix + "/lib/pkgconfig",
                 "LD_LIBRARY_PATH=" + prefix + "/lib"]
        if env:
            argv.extend(f"{key}={value}" for key, value in env.items())
        if cwd:
            argv += ["/usr/bin/env", "-C", cwd]
        argv.extend(map(str, command))
        print("+", " ".join(argv[2:]), flush=True)
        subprocess.run(argv, check=True)

    def local(relative):
        return root / relative.lstrip("/")

    def checked_port_file(package, filename):
        recipe = (upstream / package / "APKBUILD").read_text()
        expected = dict((name, value) for value, name in re.findall(r"^([a-f0-9]{128})\s+(\S+)\s*$", recipe, re.M))[filename]
        path = upstream / package / filename
        if sha(path) != expected:
            raise ValueError(f"port file checksum mismatch: {path}")
        return path

    def source(package, patches=()):
        entry = sources[package]
        archive = args.sources / entry["file"]
        if sha(archive) != entry["sha512"]:
            raise ValueError("source changed after verification")
        destination = work / package
        prepared = destination / "source-prepared.json"
        expected_inputs = {"source": entry["sha512"], "patches": {
            name: sha(checked_port_file(package, name)) for name in patches}}
        if prepared.exists():
            saved = json.loads(prepared.read_text())
            if saved["inputs"] != expected_inputs:
                raise ValueError("prepared source inputs changed")
            return saved["path"]
        destination.mkdir(exist_ok=False)
        with tarfile.open(archive) as tar:
            tar.extractall(destination, filter="data")
        directories = list(destination.iterdir())
        if len(directories) != 1 or not directories[0].is_dir():
            raise ValueError("expected one source directory")
        path = "/build/" + package + "/" + directories[0].name
        for filename in patches:
            patch = checked_port_file(package, filename)
            target = work / (package + "-" + filename)
            shutil.copyfile(patch, target)
            run("patch", "-p1", "--batch", "--forward", "-i", "/build/" + target.name, cwd=path)
        prepared.write_text(json.dumps({"path": path, "inputs": expected_inputs}, indent=2) + "\n")
        return path

    def meson(path, *options, install=True, targets=(), install_prefix=prefix):
        build = path + "/output"
        reconfigure = ["--reconfigure"] if local(build + "/meson-private/coredata.dat").exists() else []
        run("meson", "setup", *reconfigure, build, path, "--cross-file=/build/arm64.ini",
            "--wrap-mode=nodownload", "--buildtype=release", "--prefix=" + install_prefix,
            "--libdir=lib", "-Dc_link_args=-Wl,-rpath," + prefix + "/lib",
            "-Dcpp_link_args=-Wl,-rpath," + prefix + "/lib", *options)
        run("ninja", "-C", build, "-j4", *targets)
        if install:
            run("meson", "install", "-C", build, "--no-rebuild")
        return build

    def qrtr():
        meson(source("qrtr-ns-gta4l"), "-Dqrtr-ns=enabled", "-Dsystemd-service=disabled")

    def mapper():
        path = source("pd-mapper-gta4l", ["downstream-firmware.patch"])
        run("make", "-j4", "CC=aarch64-linux-gnu-gcc", "prefix=" + prefix, cwd=path)
        run("make", "install", "prefix=" + prefix, cwd=path)

    def tqftp():
        path = source("tqftpserv-gta4l", ["downstream-firmware.patch"])
        meson(path, "-Dsystemd-unit-prefix=" + prefix + "/lib/systemd/system/")
        test = checked_port_file("tqftpserv-gta4l", "translation-test.c")
        shutil.copyfile(test, local(path + "/translation-test.c"))
        run("aarch64-linux-gnu-gcc", "-DHAVE_ZSTD", "-I.", "translation-test.c", "translate.c",
            "zstd-decompress.c", "-lzstd", "-o", "translation-test", cwd=path)
        run(path + "/translation-test")

    def rpc():
        path = source("hexagonrpc-gta4l", ["downstream-fastrpc.patch"])
        shutil.copyfile(checked_port_file("hexagonrpc-gta4l", "gta4l-fastrpc.h"), local(path + "/include/gta4l-fastrpc.h"))
        meson(path, "-Dhexagonrpcd_verbose=true")
        for filename in ("kernel-abi-test.c", "gta4l-reference-uapi.h"):
            shutil.copyfile(checked_port_file("hexagonrpc-gta4l", filename), local(path + "/" + filename))
        run("aarch64-linux-gnu-gcc", "-Iinclude", "-I.", "kernel-abi-test.c", "-o", "kernel-abi-test", cwd=path)
        run(path + "/kernel-abi-test")

    def ssc():
        meson(source("libssc"))

    def sensor_proxy():
        meson(source("iio-sensor-proxy", ["downstream-fastrpc-discovery.patch", "ssc-early-claim.patch"]),
              "-Dssc-support=enabled", "-Dsystemdsystemunitdir=" + prefix + "/lib/systemd/system",
              "-Dudevrulesdir=" + prefix + "/lib/udev/rules.d")

    def turnip():
        path = source("mesa-vulkan-kgsl-gta4l")
        build = meson(path, "-Dgallium-drivers=", "-Dvulkan-drivers=freedreno", "-Dfreedreno-kmds=kgsl",
            "-Dplatforms=x11,wayland", "-Dglx=disabled", "-Degl=disabled", "-Dgbm=disabled",
            "-Dopengl=false", "-Dgles1=disabled", "-Dgles2=disabled", "-Dllvm=disabled",
            "-Dvideo-codecs=", "-Dmicrosoft-clc=disabled", "-Dvalgrind=disabled",
            "-Dlibunwind=disabled", "-Dbuild-tests=false", "-Dvulkan-layers=", "-Dtools=",
            "-Dvulkan-beta=true", install=False, targets=["src/freedreno/vulkan/libvulkan_freedreno.so"])
        destination = local("/usr/lib/gta4l-kgsl")
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local(build + "/src/freedreno/vulkan/libvulkan_freedreno.so"), destination)

    def zink():
        meson(source("mesa-zink-kgsl-gta4l", ["zink-explicit-kgsl-device.patch"]),
            "-Dgallium-drivers=zink", "-Dvulkan-drivers=", "-Dfreedreno-kmds=kgsl",
            "-Dplatforms=x11,wayland", "-Dglx=dri", "-Degl=enabled", "-Dgbm=enabled",
            "-Dopengl=true", "-Dgles1=enabled", "-Dgles2=enabled", "-Dglvnd=disabled",
            "-Dllvm=disabled", "-Dvideo-codecs=", "-Dmicrosoft-clc=disabled",
            "-Dvalgrind=disabled", "-Dlibunwind=disabled", "-Dbuild-tests=false",
            "-Dvulkan-layers=", "-Dtools=", install_prefix="/usr/lib/gta4l-zink")

    def local_helpers():
        destination = local(prefix + "/bin")
        destination.mkdir(parents=True, exist_ok=True)
        for package, filename, target in (
            ("wlfw-gta4l", "wlfw-initialize.c", "wlfw-initialize-gta4l"),
            ("device-samsung-gta4l", "gta4l-subsystem.c", "gta4l-subsystem"),
        ):
            file = work / filename
            shutil.copyfile(checked_port_file(package, filename), file)
            run("aarch64-linux-gnu-gcc", "-O2", "-Wall", "-Wextra", "-Werror", "/build/" + filename,
                "-o", prefix + "/bin/" + target)
        file = work / "gta4l-camera-pipewire.c"
        shutil.copyfile(checked_port_file("camera-pipewire-gta4l", file.name), file)
        flags = subprocess.check_output(["chroot", str(root), "/usr/local/bin/pkg-config-arm64", "--cflags", "--libs",
                                         "libpipewire-0.3", "wayland-client"], text=True).split()
        run("aarch64-linux-gnu-gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", "/build/" + file.name,
            "-o", prefix + "/bin/gta4l-camera-pipewire", *flags)

    def modemmanager():
        path = "/build/debian-sources/modemmanager-1.24.0"
        patched = local(path + "/src/mm-shared-qmi.c")
        if "gta4l_loc_unlock_progress" not in patched.read_text():
            patch = repo / "ports/samsung-gta4l/patches/debian-modemmanager-1.24-gps.patch"
            shutil.copyfile(patch, work / "debian-modemmanager-gps.patch")
            run("patch", "-p1", "--batch", "--fuzz=0", "-i", "/build/debian-modemmanager-gps.patch", cwd=path)
        meson(path, "--auto-features=disabled", "-Dplugin_qcom_soc=enabled", "-Dplugin_generic=enabled",
              "-Dmbim=false", "-Dqmi=true", "-Dqrtr=true", "-Dintrospection=false", "-Dvapi=false",
              "-Dgtk_doc=false", "-Dman=false", "-Dexamples=false", "-Dtests=false",
              "-Dbash_completion=false", "-Dpolkit=permissive", "-Dsystemd_journal=false",
              "-Dsystemd_suspend_resume=true", "-Dsystemdsystemunitdir=" + prefix + "/lib/systemd/system",
              "-Ddbus_policy_dir=" + prefix + "/share/dbus-1/system.d")

    def settings():
        path = "/build/debian-sources/gnome-control-center-48.4"
        source_file = local(path + "/panels/system/about/cc-system-details-window.c")
        if "GTA4L_ZINK_KGSL" not in source_file.read_text():
            patch = repo / "ports/samsung-gta4l/patches/debian-gnome-settings-48-renderer.patch"
            shutil.copyfile(patch, work / "debian-gnome-settings-renderer.patch")
            run("patch", "-p1", "--batch", "--fuzz=0", "-i", "/build/debian-gnome-settings-renderer.patch", cwd=path)
        meson(path, "-Ddocumentation=false", "-Dtests=false", "-Dsnap=false", "-Dprivileged_group=sudo",
              install_prefix="/usr/lib/debport-gnome-settings")

    components = {"turnip": turnip, "zink": zink, "qrtr": qrtr, "pd-mapper": mapper,
                  "tqftpserv": tqftp, "hexagonrpc": rpc, "libssc": ssc,
                  "iio-sensor-proxy": sensor_proxy, "local-helpers": local_helpers,
                  "modemmanager": modemmanager, "gnome-settings": settings}
    failures = []
    for name in args.only or components:
        receipt = receipts / (name + ".json")
        if receipt.exists() and json.loads(receipt.read_text())["status"] == "built":
            print("Already built:", name, flush=True)
            continue
        current = {"component": name, "port_revision": manifest["port_revision"], "status": "building"}
        try:
            components[name]()
            current["status"] = "built"
        except Exception as error:
            current.update(status="failed", error=str(error))
            failures.append(name)
            print("Component failed:", name, error, flush=True)
        receipt.write_text(json.dumps(current, indent=2) + "\n")
    if failures:
        raise SystemExit("Failed components: " + ", ".join(failures))


if __name__ == "__main__":
    main()
