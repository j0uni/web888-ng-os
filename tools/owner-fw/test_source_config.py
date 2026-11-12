"""Keep source-built images and the offline personalized image consistent."""
from pathlib import Path
import unittest
from fw_image import BASE_URL, UPDATER

REPO = Path(__file__).resolve().parents[2]


class OwnerSourceTests(unittest.TestCase):
    def test_recipe_and_tooling_trust_exactly_the_same_public_identity(self):
        cert = (REPO / "tools/owner-fw/owner.cert.pem").read_bytes()
        self.assertEqual(cert.count(b"-----BEGIN CERTIFICATE-----"), 1)
        self.assertNotIn(b"PRIVATE KEY", cert)
        for path in ("meta-web888/recipes-core/rauc/files/web888-ca.cert.pem",
                     "meta-web888/recipes-core/bundles/files/release-1.cert.pem"):
            self.assertEqual((REPO / path).read_bytes(), cert)

    def test_source_built_updater_matches_personalized_image(self):
        files = REPO / "meta-web888/recipes-core/web888-owner-update/files"
        self.assertEqual((files / "web888-owner-update").read_text(), UPDATER)
        self.assertEqual((files / "web888-owner-source").read_text(), BASE_URL + "\n")
        recipe = REPO / "meta-web888/recipes-core/images/web888-image.bb"
        self.assertIn('IMAGE_INSTALL += "rauc e2fsprogs-resize2fs web888-owner-update"', recipe.read_text())

    def test_new_recipe_uses_project_license_checksum(self):
        core = REPO / "meta-web888/recipes-core"
        existing = (core / "web888-setup/web888-setup.bb").read_text()
        new = (core / "web888-owner-update/web888-owner-update.bb").read_text()
        checksum = next(line for line in existing.splitlines() if line.startswith("LIC_FILES_CHKSUM"))
        self.assertIn(checksum, new)


if __name__ == "__main__":
    unittest.main()
