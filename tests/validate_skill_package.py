#!/usr/bin/env python3
"""Static package validation without loading a private browser session."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NAME = "wx-channels-download"
EXPECTED_VERSION = "1.1.0-randy.1"
REQUIRED_FILES = (
    "SKILL.md",
    "_meta.json",
    "agents/openai.yaml",
    "references/troubleshooting.md",
    "scripts/yuanbao_channels.py",
    "scripts/run_macos.sh",
    "scripts/setup_macos.sh",
    "scripts/run.ps1",
    "scripts/setup.ps1",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            fail(f"missing required file: {relative}")

    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n"):
        fail("SKILL.md must begin with YAML frontmatter")
    match = re.match(r"\A---\n(?P<header>.*?)\n---\n", skill_text, flags=re.DOTALL)
    if not match:
        fail("SKILL.md frontmatter is not closed")
    header = match.group("header")
    name = re.search(r"(?m)^name:\s*([^\n]+)$", header)
    version = re.search(r'(?m)^\s*version:\s*["\']?([^"\'\n]+)', header)
    if not name or name.group(1).strip() != EXPECTED_NAME:
        fail(f"unexpected Skill name: {name.group(1).strip() if name else None}")
    if not version or version.group(1).strip() != EXPECTED_VERSION:
        fail(f"unexpected Skill version: {version.group(1).strip() if version else None}")

    metadata = json.loads((ROOT / "_meta.json").read_text(encoding="utf-8"))
    if metadata.get("version") != EXPECTED_VERSION:
        fail("_meta.json version does not match SKILL.md")
    if metadata.get("slug") != EXPECTED_NAME:
        fail("_meta.json slug does not match Skill name")
    if metadata.get("repository") != "https://github.com/Randy0609/wx-channels-download":
        fail("_meta.json repository is missing or unexpected")

    python_path = ROOT / "scripts/yuanbao_channels.py"
    python_text = python_path.read_text(encoding="utf-8")
    ast.parse(python_text, filename=str(python_path))
    if f'SKILL_VERSION = "{EXPECTED_VERSION}"' not in python_text:
        fail("Python runtime version does not match package version")

    for relative in ("scripts/run_macos.sh", "scripts/setup_macos.sh"):
        if EXPECTED_VERSION not in (ROOT / relative).read_text(encoding="utf-8"):
            fail(f"{relative} does not report the package version")

    disallowed_suffixes = {".mp4", ".mov", ".mkv", ".part", ".sqlite", ".cookie"}
    disallowed_names = {"Cookies", "Login Data", "settings.json"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in disallowed_suffixes or path.name in disallowed_names:
            fail(f"runtime or media artifact must not be committed: {path.relative_to(ROOT)}")
        if path.stat().st_size > 1_000_000:
            fail(f"unexpected file larger than 1 MB: {path.relative_to(ROOT)}")

    print(json.dumps({
        "ok": True,
        "name": EXPECTED_NAME,
        "version": EXPECTED_VERSION,
        "required_files": len(REQUIRED_FILES),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
