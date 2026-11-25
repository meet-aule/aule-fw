import struct
import tempfile
import unittest
from pathlib import Path

import test_publish_firmware
from package_aule import package


class AulePackageTests(unittest.TestCase):
    def test_packages_only_matching_application_and_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            merged = test_publish_firmware.ReleaseTests().image(version="0.0.2", chip=9)
            app = bytes(merged[0x10000:])
            (root / "merged-binary.bin").write_bytes(merged)
            (root / "xiaozhi.bin").write_bytes(app)
            package(root, root / "release", "0.0.2")
            self.assertEqual((root / "release/aule-v0.2-0.0.2.ota.bin").read_bytes(), app)
            self.assertEqual(len((root / "release/SHA256SUMS").read_text().splitlines()), 2)
            with self.assertRaises(FileExistsError):
                package(root, root / "release", "0.0.2")

    def test_rejects_factory_wrong_version_wrong_chip_and_mismatched_app(self):
        for error in ("factory", "version", "chip", "mismatch", "capacity"):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                merged = test_publish_firmware.ReleaseTests().image(version="0.0.2", chip=5 if error == "chip" else 9)
                app = bytearray(merged[0x10000:])
                if error == "factory":
                    app = merged
                if error == "mismatch":
                    app[-1] ^= 1
                if error == "capacity":
                    struct.pack_into("<I", merged, 0x8008, 512)
                (root / "merged-binary.bin").write_bytes(merged)
                (root / "xiaozhi.bin").write_bytes(app)
                with self.assertRaises(ValueError):
                    package(root, root / "release", "0.0.3" if error == "version" else "0.0.2")
                self.assertFalse((root / "release").exists())
