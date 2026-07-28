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


def test_main_with_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling main with arguments should proceed through parse_args."""
    assert main([]) == 0
    with pytest.raises(SystemExit):
        main(["--version"])



def test_main_module_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify running kvscope as __main__."""
    import runpy

    monkeypatch.setattr("sys.argv", ["kvscope"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("kvscope.__main__", run_name="__main__")
    assert exc.value.code == 0


def test_main_parse_args_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify main returns 0 when parse_args completes."""
    from argparse import ArgumentParser
    monkeypatch.setattr(ArgumentParser, "parse_args", lambda self, args: None)
    assert main(["dummy"]) == 0



