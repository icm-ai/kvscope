"""Locate built-in data files in source checkouts and installed distributions."""

import sysconfig
from pathlib import Path


def default_profile_directory(category: str) -> Path:
    """Return a built-in profile directory, preferring installed package data."""
    installed_directory = (
        Path(sysconfig.get_path("data"))
        / "share"
        / "kvscope"
        / "profiles"
        / category
    )
    if installed_directory.is_dir():
        return installed_directory

    repository_directory = (
        Path(__file__).resolve().parents[2] / "profiles" / category
    )
    return repository_directory
