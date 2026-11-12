import hashlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import flash_card as flash
from fw_image import partitions, copy_bytes


def disk_fixture(path, marker):
    # Small file-backed roots, plus the actual 32 MiB config-partition size.
    layout = [(0x0e, 2048, 2048), (0x83, 4096, 2048),
              (0x83, 6144, 2048), (0x83, 8192, 65536)]
    mbr = bytearray(512)
    mbr[510:] = b"\x55\xaa"
    for i, (kind, start, size) in enumerate(layout):
        mbr[446+i*16+4] = kind
        struct.pack_into("<II", mbr, 446+i*16+8, start, size)
    with path.open("wb") as f:
        f.write(mbr)
        f.truncate((8192+65536)*512)
        f.seek(8192*512 + 1024 + 56)
        f.write(b"\x53\xef")
        f.seek(8192*512 + 1024 + 120)
        f.write(b"config\0")
        f.seek(8192*512 + 4096)
        f.write(marker)
    return layout


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.d = Path(self.temp.name)
        self.old, self.new = self.d / "card", self.d / "image"
        disk_fixture(self.old, b"private original configuration")
        disk_fixture(self.new, b"empty new configuration")
        self.text = self.d / "text"
        self.text.write_bytes(b"network = dhcp\n")
        self.backup = self.d / "backup"

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        return flash.save_config(self.old, self.text, self.backup)

    def test_migration_restores_original_configuration_exactly(self):
        before = flash.digest_region(self.old, 8192*512, 32 << 20)
        record = self.save()
        flash.write_and_verify(self.old, self.new, self.backup, record)
        self.assertEqual(flash.digest_region(self.old, 8192*512, 32 << 20), before)
        self.assertEqual((self.backup / "web888.txt").read_bytes(), self.text.read_bytes())

    def test_corrupt_backup_prevents_any_write(self):
        record = self.save()
        (self.backup / "config.ext4").write_bytes(b"corrupt")
        before = flash.sha(self.old)
        with self.assertRaises(ValueError):
            flash.write_and_verify(self.old, self.new, self.backup, record)
        self.assertEqual(flash.sha(self.old), before)

    def test_missing_backup_prevents_any_write(self):
        record = self.save()
        (self.backup / "config.ext4").unlink()
        before = flash.sha(self.old)
        with self.assertRaises(FileNotFoundError):
            flash.write_and_verify(self.old, self.new, self.backup, record)
        self.assertEqual(flash.sha(self.old), before)

    def test_boot_text_backup_corruption_prevents_any_write(self):
        record = self.save()
        (self.backup / "web888.txt").write_bytes(b"wrong")
        before = flash.sha(self.old)
        with self.assertRaises(ValueError):
            flash.write_and_verify(self.old, self.new, self.backup, record)
        self.assertEqual(flash.sha(self.old), before)

    def test_partial_writes_are_completed(self):
        class ShortWriter(io.BytesIO):
            def write(self, block):
                return super().write(block[:3])
        output = ShortWriter()
        copy_bytes(io.BytesIO(b"all original bytes"), output, 18)
        self.assertEqual(output.getvalue(), b"all original bytes")

    def test_zero_progress_write_fails(self):
        class StuckWriter:
            def write(self, block):
                return 0
        with self.assertRaises(OSError):
            copy_bytes(io.BytesIO(b"abc"), StuckWriter(), 3)

    def test_truncated_card_backup_fails_without_writes(self):
        with self.old.open("r+b") as f:
            f.truncate((8192+100)*512)
        before = flash.sha(self.old)
        with self.assertRaises(ValueError):
            self.save()
        self.assertEqual(flash.sha(self.old), before)

    def test_invalid_label_prevents_backup_and_write(self):
        with self.old.open("r+b") as f:
            f.seek(8192*512 + 1024 + 120)
            f.write(b"wrong!")
        before = flash.sha(self.old)
        with self.assertRaises(ValueError):
            self.save()
        self.assertFalse(self.backup.exists())
        self.assertEqual(flash.sha(self.old), before)

    def test_incompatible_new_config_size_prevents_write(self):
        record = self.save()
        with self.new.open("r+b") as f:
            f.seek(446+3*16+12)
            f.write(struct.pack("<I", 32768))
        before = flash.sha(self.old)
        with self.assertRaises(ValueError):
            flash.write_and_verify(self.old, self.new, self.backup, record)
        self.assertEqual(flash.sha(self.old), before)

    def test_write_error_stops_and_retains_backup(self):
        record = self.save()
        with patch.object(flash, "copy_bytes", side_effect=OSError("simulated write error")):
            with self.assertRaises(OSError):
                flash.write_and_verify(self.old, self.new, self.backup, record)
        self.assertEqual(flash.sha(self.backup / "config.ext4"), record["config_sha256"])

    def test_readback_error_stops_before_restore(self):
        record = self.save()
        with patch.object(flash, "digest_stream", return_value="wrong"):
            with self.assertRaisesRegex(ValueError, "read-back"):
                flash.write_and_verify(self.old, self.new, self.backup, record)
        self.assertEqual(flash.sha(self.old), flash.sha(self.new))

    def test_backup_is_private(self):
        self.save()
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.backup / "config.ext4").stat().st_mode & 0o777, 0o600)

    def test_partition_overlap_is_rejected(self):
        mbr = bytearray(self.old.read_bytes()[:512])
        struct.pack_into("<I", mbr, 446+1*16+8, 2049)
        with self.assertRaises(ValueError):
            partitions(mbr)


if __name__ == "__main__":
    unittest.main()
