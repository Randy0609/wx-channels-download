#!/usr/bin/env python3
"""Build a deterministic, runtime-artifact-free Skill ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = "wx-channels-download"
DEFAULT_VERSION = "1.1.0-randy.1"
INCLUDE = (
    "SKILL.md",
    "_meta.json",
    "README.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
    "LICENSE-RANDY-ADDITIONS.md",
    "agents/openai.yaml",
    "references/troubleshooting.md",
    "scripts/run.ps1",
    "scripts/run_macos.sh",
    "scripts/setup.ps1",
    "scripts/setup_macos.sh",
    "scripts/yuanbao_channels.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", default=DEFAULT_VERSION)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / f"{PACKAGE_ROOT}-v{args.version}.zip"

    timestamp = (2026, 8, 29, 0, 0, 0)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative in INCLUDE:
            source = ROOT / relative
            if not source.is_file():
                raise FileNotFoundError(source)
            info = zipfile.ZipInfo(f"{PACKAGE_ROOT}/{relative}", timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            executable = relative.endswith((".sh", ".py"))
            mode = stat.S_IFREG | (0o755 if executable else 0o644)
            info.external_attr = mode << 16
            info.create_system = 3
            bundle.writestr(info, source.read_bytes())

    digest = sha256(archive)
    checksum = args.output_dir / "SHA256SUMS.txt"
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "ok": True,
        "archive": str(archive),
        "sha256": digest,
        "checksum_file": str(checksum),
        "files": len(INCLUDE),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
