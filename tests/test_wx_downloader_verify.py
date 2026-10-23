"""Check failure boundaries of the independent, authentication-free media verifier."""

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/wx-downloader/scripts/verify_media.py"
SPEC = importlib.util.spec_from_file_location("wx_downloader_verify", SCRIPT)
verify_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_module)


class VerifyMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "video.mp4"

    def test_error_page_is_not_a_video(self):
        self.path.write_bytes(b"<html>authentication failed</html>")
        with self.assertRaises(ValueError):
            verify_module.verify(self.path)

    def test_expected_length_must_match(self):
        self.path.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2")
        with self.assertRaises(ValueError):
            verify_module.verify(self.path, expected_bytes=100)

    def test_partial_file_is_not_a_final_download(self):
        partial = self.path.with_suffix(".mp4.part")
        partial.write_bytes(b"\x00\x00\x00\x18ftypisom")
        with self.assertRaises(ValueError):
            verify_module.verify(partial)

    def test_missing_tools_preserve_unverified_states(self):
        self.path.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2")
        with patch.object(verify_module.shutil, "which", return_value=None):
            result = verify_module.verify(self.path)
        self.assertEqual(result["probe"]["status"], "unavailable")
        self.assertEqual(result["full_decode"]["status"], "not_requested")
        self.assertIsNone(result["expected_bytes_matched"])

    def test_missing_decoder_cannot_pass_full_decode(self):
        self.path.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2")
        with patch.object(verify_module.shutil, "which", return_value=None):
            with self.assertRaises(ValueError):
                verify_module.verify(self.path, full_decode=True)

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is not installed")
    def test_header_only_file_fails_actual_media_probe(self):
        self.path.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2")
        with self.assertRaises(ValueError):
            verify_module.verify(self.path)


if __name__ == "__main__":
    unittest.main()
