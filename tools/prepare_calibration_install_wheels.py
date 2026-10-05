#!/usr/bin/env python3
"""Explicit environment preparation; pytest itself builds/installs offline.

Run with the same Python minor/platform as pytest and a pip-equipped interpreter.
Only project runtime and build requirements are downloaded, never inference extras.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Stage dependency wheels using an explicit source before the offline suite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--no-index", action="store_true")
    parser.add_argument("--find-links", type=Path)
    args = parser.parse_args()
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = [
        *metadata["build-system"]["requires"],
        *metadata["project"]["dependencies"],
        # Older supported setuptools versions need the wheel build command.
        "wheel",
    ]
    args.wheelhouse.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--only-binary=:all:",
        "--dest",
        str(args.wheelhouse.resolve()),
    ]
    if args.no_index:
        command.append("--no-index")
    if args.find_links is not None:
        command.extend(["--find-links", str(args.find_links.resolve())])
    return subprocess.run([*command, *requirements], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
