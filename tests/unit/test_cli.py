"""Unit tests for the Phase 0 CLI boundary."""

import pytest

from kvscope import __version__
from kvscope.cli.app import build_parser, main


def test_version_argument_reports_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The version flag should use the package's single version source."""
    with pytest.raises(SystemExit) as result:
        build_parser().parse_args(["--version"])

    assert result.value.code == 0
    assert capsys.readouterr().out.strip() == f"kvscope {__version__}"


def test_main_without_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    """The empty Phase 0 command should be discoverable."""
    assert main([]) == 0
    assert "usage: kvscope" in capsys.readouterr().out
