"""Integration checks for the installable package boundary."""

import subprocess
import sys

from kvscope import __version__


def test_module_entry_point_reports_version() -> None:
    """The package should be runnable without importing optional dependencies."""
    result = subprocess.run(
        [sys.executable, "-m", "kvscope", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == f"kvscope {__version__}"
