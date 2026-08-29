#!/usr/bin/env python3
"""Verify that the release ZIP has exactly one installable Skill root."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleasePackageTests(unittest.TestCase):
    def test_release_zip_shape_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            subprocess.run(
                [sys.executable, str(ROOT / "tools/build_release.py"), "--output-dir", str(output)],
                cwd=ROOT,
                check=True,
            )
            archive = output / "wx-channels-download-v1.1.0-randy.1.zip"
            checksum_line = (output / "SHA256SUMS.txt").read_text(encoding="utf-8").strip()
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(checksum_line, f"{digest}  {archive.name}")
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                self.assertIn("wx-channels-download/SKILL.md", names)
                self.assertTrue(all(name.startswith("wx-channels-download/") for name in names))
                self.assertFalse(any(".git" in name or "__pycache__" in name for name in names))
                self.assertFalse(any(name.endswith((".mp4", ".part", "settings.json")) for name in names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
