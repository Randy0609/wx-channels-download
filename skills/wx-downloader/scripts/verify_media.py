#!/usr/bin/env python3
"""Inspect a final local MP4 without reading authentication or making network calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run_json(command: list[str], timeout: int) -> dict:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError(f"Media probe failed: {result.stderr.strip()[:1000]}")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("Media probe returned an unexpected result")
    return data


def verify(path: Path, expected_bytes: int | None = None, full_decode: bool = False,
           decode_timeout: int = 1800) -> dict:
    path = path.expanduser().resolve()
    if path.suffix.lower() != ".mp4" or not path.is_file():
        raise ValueError("Expected an existing final .mp4 file, not a .part file")
    size = path.stat().st_size
    if size == 0:
        raise ValueError("The MP4 file is empty")
    if expected_bytes is not None and (expected_bytes <= 0 or size != expected_bytes):
        raise ValueError(f"Byte count mismatch: observed {size}, expected {expected_bytes}")
    if decode_timeout <= 0:
        raise ValueError("Decode timeout must be positive")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        header = handle.read(32)
        if len(header) < 8 or header[4:8] not in (b"ftyp", b"moov", b"mdat", b"free", b"wide"):
            raise ValueError("The file does not have a recognized MP4 box header")
        digest.update(header)
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)

    report = {
        "file_path": str(path),
        "bytes": size,
        "expected_bytes_matched": None if expected_bytes is None else True,
        "mp4_header": True,
        "sha256": digest.hexdigest(),
        "probe": {"status": "unavailable"},
        "full_decode": {"status": "not_requested"},
    }
    probe = shutil.which("ffprobe")
    if probe:
        data = run_json([
            probe, "-v", "error", "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate",
            "-of", "json", str(path),
        ], 60)
        if not any(stream.get("codec_type") == "video" for stream in data.get("streams", [])):
            raise ValueError("No video stream was found")
        report["probe"] = {"status": "passed", **data}

    if full_decode:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise ValueError("Full decoding requires ffmpeg; no complete decode was performed")
        result = subprocess.run([
            ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror",
            "-i", str(path), "-map", "0:v", "-map", "0:a?", "-f", "null", "-",
        ], capture_output=True, text=True, timeout=decode_timeout)
        if result.returncode:
            raise ValueError(f"Full decoding failed: {result.stderr.strip()[:1000]}")
        report["full_decode"] = {"status": "passed"}

    if path.stat().st_size != size:
        raise ValueError("The file size changed during verification")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected-bytes", type=int)
    parser.add_argument("--full-decode", action="store_true")
    parser.add_argument("--decode-timeout", type=int, default=1800, metavar="SECONDS")
    args = parser.parse_args()
    try:
        report = verify(args.path, args.expected_bytes, args.full_decode, args.decode_timeout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
