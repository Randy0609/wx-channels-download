#!/usr/bin/env python3
"""Safety regression tests for local-only helpers."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/yuanbao_channels.py"
SPEC = importlib.util.spec_from_file_location("yuanbao_channels", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SafetyTests(unittest.TestCase):
    def test_runtime_root_can_be_isolated_for_each_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary) / "host-runtime"
            with patch.dict(os.environ, {"WX_CHANNELS_ROOT": str(isolated)}):
                self.assertEqual(MODULE.default_root(), isolated.resolve())

    def test_share_url_allowlist(self) -> None:
        value = "https://weixin.qq.com/sph/AAc5hXmYsn"
        self.assertEqual(MODULE.validate_share_url(value), value)
        for unsafe in (
            "http://weixin.qq.com/sph/AAc5hXmYsn",
            "https://example.com/sph/AAc5hXmYsn",
            "https://user:pass@weixin.qq.com/sph/AAc5hXmYsn",
            "https://weixin.qq.com/not-sph/AAc5hXmYsn",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaises(MODULE.SkillError):
                MODULE.validate_share_url(unsafe)

    def test_captured_headers_are_immediately_allowlisted(self) -> None:
        result = MODULE.capture_safe_headers({
            "Authorization": "test-only",
            "X-Device-ID": "device",
            "Cookie": "must-not-survive",
            "Referer": "must-not-survive",
            "User-Agent": "must-not-survive",
            "Host": "must-not-survive",
        })
        self.assertEqual(result, {
            "authorization": "test-only",
            "x-device-id": "device",
        })

    def test_media_url_rejects_local_or_credentialed_targets(self) -> None:
        self.assertEqual(
            MODULE.validate_media_url("https://cdn.example.com/video.mp4"),
            "https://cdn.example.com/video.mp4",
        )
        for unsafe in (
            "http://cdn.example.com/video.mp4",
            "https://localhost/video.mp4",
            "https://service.internal/video.mp4",
            "https://127.0.0.1/video.mp4",
            "https://10.0.0.8/video.mp4",
            "https://user:pass@cdn.example.com/video.mp4",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaises(MODULE.SkillError):
                MODULE.validate_media_url(unsafe)

    def test_profile_override_stays_inside_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            allowed = root / "profiles/chrome-test"
            self.assertEqual(MODULE.profile_for(root, "chrome", str(allowed)), allowed.resolve())
            with self.assertRaises(MODULE.SkillError) as caught:
                MODULE.profile_for(root, "chrome", str(Path(temporary) / "normal-browser-profile"))
            self.assertEqual(caught.exception.code, "UNSAFE_PROFILE_DIR")

    def test_preview_alias_uses_safe_name_and_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = directory / "中文 标题.mp4"
            original.write_bytes(b"test-mp4-bytes")
            preview, mode = MODULE.ensure_preview_path(
                original,
                "https://weixin.qq.com/sph/AAc5hXmYsn",
            )
            self.assertRegex(preview.name, r"^[A-Za-z0-9._-]+\.mp4$")
            self.assertEqual(preview.read_bytes(), original.read_bytes())
            self.assertIn(mode, {"hardlink", "copy"})
            if mode == "hardlink":
                self.assertEqual(os.stat(preview).st_ino, os.stat(original).st_ino)
            preview_two, _ = MODULE.ensure_preview_path(
                original,
                "https://weixin.qq.com/sph/AAc5hXmYsn",
            )
            self.assertNotEqual(preview_two, preview)

    def test_filename_cleanup(self) -> None:
        cleaned = MODULE.clean_filename('  a/b:c*?"<>|  ')
        self.assertNotRegex(cleaned, r'[<>:"/\\|?*]')
        self.assertTrue(cleaned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
