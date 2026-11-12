"""Real RAUC verification, with disposable encrypted keys only; Linux container."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import fw_image


class SignatureTests(unittest.TestCase):
    def test_trusted_untrusted_tampered_and_modified_payload(self):
        with tempfile.TemporaryDirectory(prefix="signature-test-") as td:
            d = Path(td)
            config = d / "system.conf"
            config.write_text("[system]\ncompatible=web888\nbootloader=noop\n[keyring]\ncheck-purpose=codesign\n")
            env = dict(os.environ, RAUC_KEY_PASSPHRASE="disposable-test-password")
            def run(*cmd, good=True):
                if cmd[0] == "rauc":
                    cmd = ("rauc", f"--conf={config}", *cmd[1:])
                p = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                if good:
                    self.assertEqual(p.returncode, 0, p.stdout)
                else:
                    self.assertNotEqual(p.returncode, 0, p.stdout)
                return p.stdout
            for name in ("owner", "untrusted"):
                run("openssl", "req", "-new", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "1",
                    "-passout", "env:RAUC_KEY_PASSPHRASE", "-subj", f"/CN={name}/",
                    "-addext", "basicConstraints=critical,CA:TRUE",
                    "-addext", "keyUsage=critical,digitalSignature,keyCertSign,cRLSign",
                    "-addext", "extendedKeyUsage=codeSigning",
                    "-keyout", str(d/f"{name}.key"), "-out", str(d/f"{name}.crt"))
            content = d/"content"
            content.mkdir()
            # Payload is incompressible, so damaging it tests full verity verification.
            (content/"rootfs.ext4").write_bytes(os.urandom(2 << 20))
            (content/"manifest.raucm").write_text("[update]\ncompatible=web888\nversion=test\n[bundle]\nformat=verity\n[image.rootfs]\nfilename=rootfs.ext4\n")
            bundle = d/"test.raucb"
            run("rauc", f"--cert={d/'owner.crt'}", f"--key={d/'owner.key'}", f"--keyring={d/'owner.crt'}",
                "bundle", "--mksquashfs-args=-processors 2", str(content), str(bundle))
            run("rauc", f"--keyring={d/'owner.crt'}", "info", str(bundle))
            run("rauc", f"--keyring={d/'untrusted.crt'}", "info", str(bundle), good=False)
            run("rauc", f"--keyring={d/'owner.crt'}", "extract", str(bundle), str(d/"extracted"))
            self.assertEqual((d/"extracted/rootfs.ext4").read_bytes(), (content/"rootfs.ext4").read_bytes())
            # Signed CMS footer corruption must fail even the header/signature check.
            signature_bad = d/"signature-bad.raucb"
            damaged = bytearray(bundle.read_bytes())
            damaged[-16] ^= 1
            signature_bad.write_bytes(damaged)
            run("rauc", f"--keyring={d/'owner.crt'}", "info", str(signature_bad), good=False)
            # Payload damage can leave the CMS valid; full extract must still reject it.
            payload_bad = d/"payload-bad.raucb"
            damaged = bytearray(bundle.read_bytes())
            damaged[8192] ^= 1
            payload_bad.write_bytes(damaged)
            run("rauc", f"--keyring={d/'owner.crt'}", "extract", str(payload_bad), str(d/"bad-extracted"), good=False)
            # Exercise the actual packager on a real small ext4 filesystem too.
            root = d / "real-root.ext4"
            with root.open("wb") as f:
                f.truncate(16 << 20)
            run("mkfs.ext4", "-q", "-F", "-L", "rootA", str(root))
            for directory in ("/usr", "/usr/lib", "/usr/lib/rauc", "/usr/bin", "/etc"):
                fw_image.debugfs(root, f"mkdir {directory}", True)
            target_config = ("[system]\ncompatible=web888\nbootloader=uboot\n"
                             "[keyring]\npath=" + fw_image.KEYRING + "\ncheck-purpose=codesign\n"
                             "[slot.rootfs.0]\ndevice=/dev/mmcblk0p2\ntype=ext4\nbootname=A\n"
                             "[slot.rootfs.1]\ndevice=/dev/mmcblk0p3\ntype=ext4\nbootname=B\n")
            fw_image.replace_file(root, "/usr/lib/rauc/system.conf", target_config.encode())
            fw_image.replace_file(root, "/usr/bin/web888-owner-update", fw_image.UPDATER.encode(), True)
            fw_image.replace_file(root, "/etc/web888-owner-source", (fw_image.BASE_URL + "\n").encode())
            fw_image.replace_file(root, fw_image.KEYRING, (d/"owner.crt").read_bytes())
            args = SimpleNamespace(rootfs=str(root), cert=str(d/"owner.crt"), key=str(d/"owner.key"),
                                   output=str(d/"actual-packager.raucb"), version="test-owner")
            # A fresh one-day certificate has slightly less than one day remaining;
            # checkend is independently enforced by production tooling (one full day).
            # Reissue the same test identity for two days, updating the embedded cert.
            run("openssl", "req", "-new", "-x509", "-key", str(d/"owner.key"),
                "-passin", "env:RAUC_KEY_PASSPHRASE", "-sha256", "-days", "2", "-subj", "/CN=owner/",
                "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,digitalSignature,keyCertSign,cRLSign",
                "-addext", "extendedKeyUsage=codeSigning", "-out", str(d/"owner.crt"))
            fw_image.replace_file(root, fw_image.KEYRING, (d/"owner.crt").read_bytes())
            with patch.dict(os.environ, RAUC_KEY_PASSPHRASE="disposable-test-password"):
                fw_image.bundle(args)
            run("rauc", f"--keyring={d/'owner.crt'}", "extract", args.output, str(d/"actual-extracted"))
            self.assertEqual((d/"actual-extracted/rootfs.ext4").read_bytes(), root.read_bytes())
            args.cert = str(d/"untrusted.crt")
            args.output = str(d/"must-not-exist.raucb")
            with self.assertRaisesRegex(ValueError, "does not retain"):
                fw_image.bundle(args)
            self.assertFalse(Path(args.output).exists())
            args.cert = str(d/"owner.crt")
            fw_image.debugfs(root, "mkdir /etc/rauc", True)
            fw_image.replace_file(root, "/etc/rauc/system.conf", target_config.replace(fw_image.KEYRING, "/official.pem").encode())
            with self.assertRaisesRegex(ValueError, "Unsafe effective RAUC configuration"):
                fw_image.bundle(args)
            self.assertFalse(Path(args.output).exists())


if __name__ == "__main__":
    unittest.main()
