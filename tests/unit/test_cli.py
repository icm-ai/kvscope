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


def test_cli_hardware_subcommands(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test hardware list, show, and budget CLI commands."""
    from decimal import Decimal

    from kvscope.domain.enums import MemoryTopology
    from kvscope.domain.evidence import Evidence
    from kvscope.domain.hardware import HardwareProfile, MemoryQuantityInput
    from kvscope.registries.hardware import HardwareRegistry

    hw_prof = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )
    custom_hw_reg = HardwareRegistry([hw_prof])
    monkeypatch.setattr(
        "kvscope.cli.app.get_default_hardware_registry",
        lambda: custom_hw_reg,
    )
    monkeypatch.setattr(
        "kvscope.resolvers.hardware.get_default_hardware_registry",
        lambda: custom_hw_reg,
    )

    assert main(["hardware", "list"]) == 0
    out_list = capsys.readouterr().out
    assert "Registered Hardware Profiles" in out_list

    # Hardware show (terminal & json)
    assert main(["hardware", "show", "gpu-16g"]) == 0
    out_show = capsys.readouterr().out
    assert "Hardware Profile: gpu-16g" in out_show

    assert main(["hardware", "show", "gpu-16g", "--format", "json"]) == 0
    out_show_json = capsys.readouterr().out
    assert '"profile_id": "gpu-16g"' in out_show_json

    # Hardware budget (terminal, json, markdown)
    assert main(["hardware", "budget", "gpu-16g"]) == 0
    out_budget = capsys.readouterr().out
    assert "Hardware Memory Budget" in out_budget

    assert main(["hardware", "budget", "gpu-16g", "--format", "json"]) == 0
    out_budget_json = capsys.readouterr().out
    assert '"physical_total_bytes"' in out_budget_json

    assert main(["hardware", "budget", "gpu-16g", "--format", "markdown"]) == 0
    out_budget_md = capsys.readouterr().out
    assert "## Non-Model Reserves Breakdown" in out_budget_md


def test_cli_backend_subcommands(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test backend list and show CLI commands with a mock registered profile."""

    from kvscope.domain.backend import BackendMemoryModel, BackendProfile
    from kvscope.domain.enums import Confidence, ProfileStatus
    from kvscope.domain.evidence import Evidence
    from kvscope.registries.backends import BackendRegistry

    prof = BackendProfile(
        schema_version="0.1",
        profile_id="vllm-test",
        backend_id="vllm",
        display_name="vLLM Test",
        version_specifier=">=0.4.0",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    custom_reg = BackendRegistry([prof])
    monkeypatch.setattr(
        "kvscope.cli.app.get_default_backend_registry",
        lambda: custom_reg,
    )
    monkeypatch.setattr(
        "kvscope.resolvers.backend.get_default_backend_registry",
        lambda: custom_reg,
    )

    assert main(["backend", "list"]) == 0
    out_list = capsys.readouterr().out
    assert "vllm-test" in out_list

    assert main(["backend", "show", "vllm"]) == 0
    out_show = capsys.readouterr().out
    assert "Backend Profile: vllm-test" in out_show

    assert main(["backend", "show", "vllm", "--format", "json"]) == 0
    out_json = capsys.readouterr().out
    assert '"profile_id": "vllm-test"' in out_json


def test_cli_estimate_overhead_subcommand(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test estimate-overhead CLI command across terminal, json, and md formats."""
    from decimal import Decimal

    from kvscope.domain.backend import BackendMemoryModel, BackendProfile
    from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
    from kvscope.domain.evidence import Evidence
    from kvscope.domain.hardware import HardwareProfile, MemoryQuantityInput
    from kvscope.registries.backends import BackendRegistry
    from kvscope.registries.hardware import HardwareRegistry

    prof = BackendProfile(
        schema_version="0.1",
        profile_id="vllm-test",
        backend_id="vllm",
        display_name="vLLM Test",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    custom_reg = BackendRegistry([prof])
    monkeypatch.setattr(
        "kvscope.resolvers.backend.get_default_backend_registry",
        lambda: custom_reg,
    )

    hw_prof = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )
    custom_hw_reg = HardwareRegistry([hw_prof])
    monkeypatch.setattr(
        "kvscope.resolvers.hardware.get_default_hardware_registry",
        lambda: custom_hw_reg,
    )

    cmd = [
        "estimate-overhead",
        "--backend",
        "vllm",
        "--hardware",
        "gpu-16g",
        "--resident-weight-bytes",
        "4294967296",
        "--parameter-count",
        "7000000000",
    ]

    assert main(cmd) == 0
    out_term = capsys.readouterr().out
    assert "Runtime Overhead Estimate" in out_term

    assert main([*cmd, "--format", "json"]) == 0
    out_json = capsys.readouterr().out
    assert '"total_runtime_overhead"' in out_json

    assert main([*cmd, "--format", "markdown"]) == 0
    out_md = capsys.readouterr().out
    assert "## Runtime Overhead Component Breakdown" in out_md
