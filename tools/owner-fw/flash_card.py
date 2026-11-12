#!/usr/bin/env python3
"""Owner-operated macOS card migration. Never run this from automated checks."""
import argparse
from datetime import datetime
import hashlib
import json
import lzma
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from fw_image import partitions, sha, copy_bytes


def digest_region(path, offset, size):
    with open(path, "rb", buffering=0) as f:
        return digest_stream(f, offset, size)


def digest_stream(f, offset, size):
    h = hashlib.sha256()
    f.seek(offset)
    while size:
        block = f.read(min(size, 4 << 20))
        if not block:
            raise ValueError("Short read from card")
        h.update(block)
        size -= len(block)
    return h.hexdigest()


def config_region(disk):
    with open(disk, "rb", buffering=0) as f:
        layout = partitions(f.read(512))
        _, offset, size = layout[3]
        if size != 32 << 20:
            raise ValueError("Unexpected configuration-partition size")
        f.seek(offset + 1024)
        sb = f.read(1024)
        if sb[56:58] != b"\x53\xef" or sb[120:136].rstrip(b"\0") != b"config":
            raise ValueError("Expected ext4 filesystem labeled config")
    return offset, size


def save_config(disk, boot_text, directory):
    """Complete, fsync and verify backups before returning a write capability."""
    offset, size = config_region(disk)
    directory = Path(directory)
    directory.mkdir(mode=0o700)
    text = directory / "web888.txt"
    config = directory / "config.ext4"
    for dest in (text, config):
        dest.touch(mode=0o600, exist_ok=False)
    text.write_bytes(Path(boot_text).read_bytes())
    with open(disk, "rb", buffering=0) as src, config.open("wb") as dst:
        src.seek(offset)
        copy_bytes(src, dst, size)
        dst.flush()
        os.fsync(dst.fileno())
    with text.open("rb") as f:
        os.fsync(f.fileno())
    digest = sha(config)
    if config.stat().st_size != size or digest != digest_region(disk, offset, size):
        raise ValueError("Configuration backup verification failed; card untouched")
    record = dict(config_sha256=digest, text_sha256=sha(text), offset=offset, size=size)
    (directory / "backup.json").write_text(json.dumps(record, indent=2) + "\n")
    os.chmod(directory / "backup.json", 0o600)
    with (directory / "backup.json").open("rb") as f:
        os.fsync(f.fileno())
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return record


def write_and_verify(disk, image, backup, record):
    """Low-level migration, also exercised against file-backed test disks."""
    # Revalidate durable backup and geometry immediately before writes.
    config = Path(backup) / "config.ext4"
    if sha(config) != record["config_sha256"] or config.stat().st_size != record["size"]:
        raise ValueError("Backup missing/corrupted; refusing to write")
    if sha(Path(backup) / "web888.txt") != record["text_sha256"]:
        raise ValueError("Boot configuration backup missing/corrupted; refusing to write")
    new_offset, new_size = config_region(image)
    if new_size != record["size"]:
        raise ValueError("New configuration partition is incompatible")
    expected_image = sha(image)
    with open(disk, "r+b", buffering=0) as dst, open(image, "rb") as src:
        dst.seek(0)
        copy_bytes(src, dst, Path(image).stat().st_size)
        os.fsync(dst.fileno())
        print("Firmware write complete; verifying read-back", flush=True)
        if digest_stream(dst, 0, Path(image).stat().st_size) != expected_image:
            raise ValueError("Image read-back verification failed; do not boot this card")
        print("Firmware verified; restoring configuration", flush=True)
        # Keep this writable raw-device descriptor open until restoration finishes.
        # Closing it between phases lets macOS auto-mount FAT and block reopening.
        with config.open("rb") as configuration:
            dst.seek(new_offset)
            copy_bytes(configuration, dst, new_size)
        os.fsync(dst.fileno())
        if digest_stream(dst, new_offset, new_size) != record["config_sha256"]:
            raise ValueError("Configuration restoration verification failed; do not boot")


def disk_info(target):
    return plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", str(target)]))


def diskutil(*args):
    subprocess.run(["/usr/sbin/diskutil", *map(str, args)], check=True)


def own_backup(directory):
    uid, gid = int(os.environ.get("SUDO_UID", os.getuid())), int(os.environ.get("SUDO_GID", os.getgid()))
    for path in [directory, *directory.iterdir()]:
        os.chown(path, uid, gid)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared", type=Path, default=Path(__file__).resolve().parent / "prepared")
    p.add_argument("--restore-backup", type=Path, help="Recovery: reuse an original verified backup; never back up the partially written card")
    p.add_argument("--device", help="Recovery only: whole card device, e.g. /dev/disk26; recheck identifier first")
    p.add_argument("--confirm-device", help="Noninteractive confirmation of a previously inspected whole-device identifier")
    args = p.parse_args()
    if sys.platform != "darwin" or os.geteuid() != 0:
        raise ValueError("Run this in macOS Terminal with sudo python3 flash_card.py")
    boot = Path("/Volumes/WEB888")
    recovery = args.restore_backup is not None
    if recovery:
        if not args.device or not re.fullmatch(r"/dev/disk[0-9]+", args.device):
            raise ValueError("Recovery requires --device /dev/diskN, identified again with diskutil list")
        whole = args.device.removeprefix("/dev/")
    else:
        if args.device:
            raise ValueError("Explicit --device is allowed only with --restore-backup")
        info = disk_info(boot)
        whole = info.get("ParentWholeDisk", "")
        if info.get("MountPoint") != str(boot) or info.get("VolumeName") != "WEB888" or not re.fullmatch(r"disk[0-9]+", whole):
            raise ValueError("Could not identify the mounted WEB888 card safely")
    whole_info = disk_info("/dev/" + whole)
    if not whole_info.get("RemovableMedia") or whole_info.get("VirtualOrPhysical") == "Virtual":
        raise ValueError("Target is not a removable physical card")
    raw = Path("/dev/r" + whole)
    prepared = args.prepared.resolve()
    meta = json.loads((prepared / "metadata.json").read_text())
    image_name = meta.get("image_filename", "web888-owner-v0.8.0.img.xz")
    if Path(image_name).name != image_name:
        raise ValueError("Invalid image filename in metadata")
    compressed = prepared / image_name
    if sha(compressed) != meta["compressed_sha256"]:
        raise ValueError("Prepared image checksum mismatch")
    backup = args.restore_backup.resolve() if recovery else prepared.parent.parent / ("web888-config-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    print(f"Target: /dev/{whole}, {whole_info.get('TotalSize')} bytes, {whole_info.get('MediaName', '')}", flush=True)
    if recovery:
        record = json.loads((backup / "backup.json").read_text())
        if sha(backup / "config.ext4") != record["config_sha256"] or sha(backup / "web888.txt") != record["text_sha256"]:
            raise ValueError("Recovery backup checksum mismatch")
    else:
        print("Backing up configuration before any card writes", flush=True)
        try:
            record = save_config(raw, boot / "web888.txt", backup)
        finally:
            if backup.exists():
                own_backup(backup)
    print(f"Verified configuration backup: {backup}", flush=True)
    with tempfile.TemporaryDirectory(prefix=".flash-", dir=prepared.parent) as td:
        image = Path(td) / "disk.img"
        with lzma.open(compressed, "rb") as src, image.open("wb") as dst:
            shutil.copyfileobj(src, dst, 4 << 20)
        if sha(image) != meta["image_sha256"]:
            raise ValueError("Decompressed image checksum mismatch")
        if image.stat().st_size > whole_info["TotalSize"]:
            raise ValueError("Image is larger than the card")
        config_region(image)
        confirm = f"UPDATE {args.confirm_device}" if args.confirm_device else input(f"This replaces firmware on /dev/{whole}. Type UPDATE {whole} to continue: ")
        if confirm != f"UPDATE {whole}":
            raise ValueError("Cancelled; card untouched; configuration backup retained")
        if (not recovery and disk_info(boot).get("ParentWholeDisk") != whole) or disk_info("/dev/" + whole).get("TotalSize") != whole_info["TotalSize"]:
            raise ValueError("Target card changed; refusing to write")
        if not recovery and digest_region(raw, record["offset"], record["size"]) != record["config_sha256"]:
            raise ValueError("Card configuration changed since backup; refusing to write")
        diskutil("unmountDisk", "/dev/" + whole)
        print("Writing firmware, reading it back, and restoring Linux configuration", flush=True)
        write_and_verify(raw, image, backup, record)
        diskutil("mount", "/dev/" + whole + "s1")
        mounted = Path(disk_info("/dev/" + whole + "s1")["MountPoint"])
        # FAT volume may receive a different mount path; use diskutil's result.
        shutil.copyfile(backup / "web888.txt", mounted / "web888.txt")
        with (mounted / "web888.txt").open("rb") as f:
            os.fsync(f.fileno())
        if sha(mounted / "web888.txt") != record["text_sha256"]:
            raise ValueError("Boot configuration restoration failed; do not boot")
        os.sync()
        diskutil("eject", "/dev/" + whole)
    print("Firmware and both configuration sources verified; card ejected.")
    print(f"Keep this private configuration backup: {backup}")
    result = prepared.parent / "flash-result.json"
    result.write_text(json.dumps(dict(status="verified-and-ejected", device=whole,
                                     completed=datetime.now().astimezone().isoformat(),
                                     backup=str(backup), image_sha256=meta["image_sha256"],
                                     config_sha256=record["config_sha256"],
                                     text_sha256=record["text_sha256"]), indent=2) + "\n")
    os.chown(result, int(os.environ.get("SUDO_UID", os.getuid())), int(os.environ.get("SUDO_GID", os.getgid())))


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f"STOP: {error}", file=sys.stderr)
        print("If writing had started, do not boot. Keep the verified config backup and repeat the documented recovery procedure.", file=sys.stderr)
        sys.exit(1)
