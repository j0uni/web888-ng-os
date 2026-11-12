#!/usr/bin/env python3
"""Offline WEB888 image personalization. Run in the bundled Linux container."""
import argparse
import configparser
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

BASE_URL = "https://jouni.kapsi.fi/web888fw/"
KEYRING = "/usr/lib/rauc/web888-ca.cert.pem"
UPDATER = '''#!/bin/sh
set -eu
# Explicit manual update; RAUC verifies the owner's signature before installation.
name=${1:-latest.raucb}
case "$name" in
  *[!A-Za-z0-9._-]*|''|.*) echo "Expected a bundle filename" >&2; exit 2 ;;
esac
case "$name" in *.raucb) ;; *) echo "Expected a .raucb bundle" >&2; exit 2 ;; esac
exec rauc install "https://jouni.kapsi.fi/web888fw/$name"
'''


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def run(*args):
    p = subprocess.run([str(a) for a in args], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f"{args[0]} failed ({p.returncode}):\n{p.stdout}")
    return p.stdout


def partitions(mbr):
    if len(mbr) != 512 or mbr[510:] != b"\x55\xaa":
        raise ValueError("Not an MBR disk")
    result = []
    for i in range(4):
        entry = mbr[446 + i * 16:462 + i * 16]
        start, count = struct.unpack_from("<II", entry, 8)
        result.append((entry[4], start * 512, count * 512))
    ends = [0]
    for kind, start, length in result:
        if not kind or not length or start < max(ends):
            raise ValueError("Missing, overlapping or unordered partition")
        ends.append(start + length)
    if [p[0] for p in result][1:] != [0x83] * 3:
        raise ValueError("Expected three Linux partitions")
    return result


def copy_bytes(src, dst, count):
    while count:
        block = src.read(min(count, 4 * 1024 * 1024))
        if not block:
            raise ValueError("Unexpected end of image")
        pending = memoryview(block)
        while pending:
            written = dst.write(pending)
            if written is None or written <= 0:
                raise OSError("Destination made no write progress")
            pending = pending[written:]
        count -= len(block)


def debugfs(image, command, write=False):
    return run("debugfs", *(["-w"] if write else []), "-R", command, image)


def replace_file(image, path, payload, executable=False):
    # Temporary paths are generated without whitespace or debugfs metacharacters.
    with tempfile.TemporaryDirectory(prefix="web888-") as d:
        source, check = Path(d) / "input", Path(d) / "output"
        source.write_bytes(payload)
        if "Inode:" in debugfs(image, f"stat {path}"):
            debugfs(image, f"rm {path}", True)
        debugfs(image, f"write {source} {path}", True)
        debugfs(image, f"set_inode_field {path} mode {'0100755' if executable else '0100644'}", True)
        debugfs(image, f"dump {path} {check}")
        if not check.exists() or check.read_bytes() != payload:
            raise RuntimeError(f"Could not verify {path} in {image}")


def image_file(image, path):
    with tempfile.TemporaryDirectory(prefix="web888-read-") as d:
        output = Path(d) / "data"
        debugfs(image, f"dump {path} {output}")
        if not output.exists():
            raise ValueError(f"Required image file missing: {path}")
        return output.read_bytes()


def validate_runtime(root):
    # Match RAUC's precedence, so an /etc override cannot silently restore
    # official trust while a matching unused owner certificate passes checks.
    for path in ("/etc/rauc/system.conf", "/run/rauc/system.conf", "/usr/lib/rauc/system.conf"):
        if "Inode:" in debugfs(root, f"stat {path}"):
            settings = configparser.ConfigParser(interpolation=None)
            settings.read_string(image_file(root, path).decode())
            break
    else:
        raise ValueError("Rootfs has no effective RAUC system.conf")
    expected = {("system", "compatible"): "web888", ("system", "bootloader"): "uboot",
                ("keyring", "path"): KEYRING,
                ("slot.rootfs.0", "device"): "/dev/mmcblk0p2",
                ("slot.rootfs.0", "type"): "ext4", ("slot.rootfs.0", "bootname"): "A",
                ("slot.rootfs.1", "device"): "/dev/mmcblk0p3",
                ("slot.rootfs.1", "type"): "ext4", ("slot.rootfs.1", "bootname"): "B"}
    for (section, key), value in expected.items():
        if settings.get(section, key, fallback=None) != value:
            raise ValueError(f"Unsafe effective RAUC configuration: {section}.{key}")
    if settings.get("keyring", "check-purpose", fallback=None) not in ("codesign", "codesign-rauc"):
        raise ValueError("Effective RAUC configuration must enforce code signing")
    if image_file(root, "/etc/web888-owner-source") != (BASE_URL + "\n").encode():
        raise ValueError("Rootfs does not retain the owner update source")
    if image_file(root, "/usr/bin/web888-owner-update") != UPDATER.encode():
        raise ValueError("Rootfs does not retain the matching owner updater")


def prepare(args):
    source, certificate, output = map(Path, (args.source, args.cert, args.output))
    base_version = getattr(args, "base_version", "v0.8.0")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,79}", base_version):
        raise ValueError("Invalid base version")
    image_name = f"web888-owner-{base_version}.img.xz"
    if sha(source) != args.sha256.lower():
        raise ValueError("Source image checksum mismatch")
    cert = certificate.read_bytes()
    if cert.count(b"-----BEGIN CERTIFICATE-----") != 1 or b"PRIVATE KEY" in cert:
        raise ValueError("Supply exactly one public owner certificate")
    run("openssl", "x509", "-in", certificate, "-noout", "-checkend", "86400")
    if output.exists():
        raise ValueError("Output directory already exists; refusing replacement")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output.parent) as td:
        temp = Path(td)
        disk = temp / "web888-owner.img"
        print("Decompressing verified image", flush=True)
        with lzma.open(source, "rb") as src, disk.open("wb") as dst:
            shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
        with disk.open("rb") as f:
            mbr = f.read(512)
        parts = partitions(mbr)
        if [p[2] for p in parts] != [64 << 20, 512 << 20, 512 << 20, 32 << 20]:
            raise ValueError("Unexpected WEB888 partition sizes")
        if max(p[1] + p[2] for p in parts) > disk.stat().st_size:
            raise ValueError("Truncated source image")
        original_regions = []
        with disk.open("rb") as f:
            # All bytes outside roots must remain exactly unchanged.
            for start, size in [(0, parts[1][1]),
                                (parts[2][1] + parts[2][2], disk.stat().st_size - parts[2][1] - parts[2][2])]:
                f.seek(start)
                original_regions.append((start, size, hashlib.sha256(f.read(size)).hexdigest()))
        for index in (1, 2):
            print(f"Personalizing root slot {'AB'[index-1]}", flush=True)
            root = temp / f"root-{index}.ext4"
            with disk.open("rb") as src, root.open("wb") as dst:
                src.seek(parts[index][1])
                copy_bytes(src, dst, parts[index][2])
            run("e2fsck", "-f", "-n", root)
            replace_file(root, KEYRING, cert)
            replace_file(root, "/usr/bin/web888-owner-update", UPDATER.encode(), True)
            replace_file(root, "/etc/web888-owner-source", (BASE_URL + "\n").encode())
            run("e2fsck", "-f", "-n", root)
            with disk.open("r+b") as dst, root.open("rb") as src:
                dst.seek(parts[index][1])
                copy_bytes(src, dst, parts[index][2])
            if index == 2:
                root.unlink()
        with disk.open("rb") as f:
            for start, size, expected in original_regions:
                f.seek(start)
                if hashlib.sha256(f.read(size)).hexdigest() != expected:
                    raise RuntimeError("Image bytes outside root slots were changed")
        # Export the personalized root for repeatable owner-signed OTA packaging.
        root = temp / "root-1.ext4"
        root.rename(temp / "rootfs.ext4")
        image_hash = sha(disk)
        print("Compressing personalized image", flush=True)
        with disk.open("rb") as src, lzma.open(temp / image_name, "wb", preset=3) as dst:
            shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
        disk.unlink()
        shutil.copyfile(certificate, temp / "owner.cert.pem")
        metadata = dict(base_version=base_version, image_filename=image_name, base_sha256=args.sha256,
                        update_source=BASE_URL, trusted_certificate_sha256=sha(certificate),
                        image_sha256=image_hash, compressed_sha256=sha(temp / image_name),
                        rootfs_sha256=sha(temp / "rootfs.ext4"), partitions=parts,
                        tooling=dict(rauc=run("rauc", "--version").strip(),
                                     openssl=run("openssl", "version").strip()),
                        changes=[KEYRING, "/usr/bin/web888-owner-update", "/etc/web888-owner-source"],
                        validation="Both root filesystems passed e2fsck -fn; inserted files extracted and compared; all bytes outside root slots unchanged")
        (temp / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        # Copy only completed artifacts; temporary directory is never a published release.
        temp.rename(output)
    print(f"Prepared {output}", flush=True)


def bundle(args):
    root, cert, key, out = map(Path, (args.rootfs, args.cert, args.key, args.output))
    if out.exists():
        raise ValueError("Bundle exists; refusing replacement")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,79}", args.version):
        raise ValueError("Invalid version")
    if root.stat().st_size > 512 << 20:
        raise ValueError("Root image exceeds the 512 MiB slot")
    run("e2fsck", "-f", "-n", root)
    with tempfile.TemporaryDirectory(prefix="web888-bundle-") as td:
        temp = Path(td)
        embedded = temp / "embedded.cert.pem"
        debugfs(root, f"dump {KEYRING} {embedded}")
        if not embedded.exists() or embedded.read_bytes() != cert.read_bytes():
            raise ValueError("Rootfs does not retain this owner signing identity")
        validate_runtime(root)
        run("openssl", "x509", "-in", cert, "-noout", "-checkend", "86400")
        shutil.copyfile(root, temp / "rootfs.ext4")
        (temp / "manifest.raucm").write_text(f"[update]\ncompatible=web888\nversion={args.version}\n\n[bundle]\nformat=verity\n\n[image.rootfs]\nfilename=rootfs.ext4\n")
        host_config = temp.parent / (temp.name + "-signing.conf")
        host_config.write_text(f"[system]\ncompatible=web888\nbootloader=noop\n[keyring]\npath={cert}\ncheck-purpose=codesign\n")
        # Inherit terminal input for the encrypted signing-key passphrase.
        command = ["rauc", f"--conf={host_config}", f"--cert={cert}", f"--key={key}", f"--keyring={cert}",
                   "bundle", "--mksquashfs-args=-processors 2", str(temp), str(out)]
        try:
            subprocess.run(command, check=True)
            print(run("rauc", f"--conf={host_config}", f"--keyring={cert}", "info", out))
        finally:
            host_config.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    for name in ("source", "sha256", "cert", "output"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--base-version", default="v0.8.0")
    p.set_defaults(handler=prepare)
    p = commands.add_parser("bundle")
    for name in ("rootfs", "cert", "key", "output", "version"):
        p.add_argument("--" + name, required=True)
    p.set_defaults(handler=bundle)
    args = parser.parse_args()
    args.handler(args)
