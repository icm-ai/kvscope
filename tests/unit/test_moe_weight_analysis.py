"""Tests for static MoE metadata in feasibility reports."""

import json
from pathlib import Path

from kvscope.cli.app import main


def _write_moe_config(path: Path) -> None:
    config = {
        "model_id": "qwen-moe-test",
        "model_type": "qwen2_moe",
        "num_hidden_layers": 4,
        "hidden_size": 512,
        "num_attention_heads": 8,
        "num_key_value_heads": 2,
        "intermediate_size": 1024,
        "vocab_size": 1000,
        "parameter_count": 1_000_000_000,
        "active_parameter_count": 100_000_000,
        "num_experts": 8,
        "num_experts_per_tok": 2,
    }
    path.write_text(json.dumps(config), encoding="utf-8")


def test_analyze_reports_moe_counts_without_reducing_resident_weights(
    tmp_path: Path, capsys
) -> None:
    model_config = tmp_path / "config.json"
    _write_moe_config(model_config)
    arguments = [
        "analyze",
        str(model_config),
        "--hardware",
        "generic-discrete-16gib",
        "--backend",
        "vllm",
        "--context",
        "4096",
        "--format",
        "json",
    ]

    assert main(arguments) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["moe_weight_analysis"] == {
        "total_parameter_count": 1_000_000_000,
        "active_parameter_count": 100_000_000,
        "num_experts": 8,
        "num_experts_per_tok": 2,
        "resident_weight_basis": "total_parameter_count",
    }
    assert (
        report["aggregation"]["resident_weights"]["memory"]["expected_bytes"]
        == 2_000_000_000
    )

    assert main([*arguments[:-1], "terminal"]) == 0
    terminal = capsys.readouterr().out
    assert "MoE Weight Metadata" in terminal
    assert "active parameters do not imply" in terminal
    assert main([*arguments[:-1], "markdown"]) == 0
    markdown = capsys.readouterr().out
    assert "## MoE Weight Metadata" in markdown
    assert "inactive expert weights are not assumed to be offloaded" in markdown


def test_compare_and_sweep_reports_include_moe_analysis(tmp_path: Path, capsys) -> None:
    model_config = tmp_path / "config.json"
    _write_moe_config(model_config)
    compare_arguments = [
        "compare",
        str(model_config),
        "--target",
        "generic-discrete-8gib=vllm",
        "--target",
        "generic-discrete-16gib=vllm",
        "--context",
        "4096",
        "--format",
        "json",
    ]

    assert main(compare_arguments) == 0
    comparison = json.loads(capsys.readouterr().out)
    assert [
        result["report"]["moe_weight_analysis"]["active_parameter_count"]
        for result in comparison["targets"]
    ] == [100_000_000, 100_000_000]
    assert all(
        result["report"]["aggregation"]["resident_weights"]["memory"][
            "expected_bytes"
        ]
        == 2_000_000_000
        for result in comparison["targets"]
    )
    assert main([*compare_arguments[:-1], "terminal"]) == 0
    assert "MoE Weight Metadata" in capsys.readouterr().out
    assert main([*compare_arguments[:-1], "markdown"]) == 0
    assert "## MoE Weight Metadata" in capsys.readouterr().out

    sweep_arguments = [
        "sweep",
        str(model_config),
        "--target",
        "generic-discrete-16gib=vllm",
        "--contexts",
        "2048",
        "4096",
        "--format",
        "json",
    ]
    assert main(sweep_arguments) == 0
    sweep = json.loads(capsys.readouterr().out)
    assert all(
        point["comparison"]["targets"][0]["report"]["moe_weight_analysis"][
            "num_experts"
        ]
        == 8
        for point in sweep["points"]
    )
    assert all(
        point["comparison"]["targets"][0]["report"]["aggregation"][
            "resident_weights"
        ]["memory"]["expected_bytes"]
        == 2_000_000_000
        for point in sweep["points"]
    )
    assert main([*sweep_arguments[:-1], "markdown"]) == 0
    assert "## MoE Weight Metadata" in capsys.readouterr().out


def test_analyze_rejects_parameter_override_below_active_parameter_count(
    tmp_path: Path, capsys
) -> None:
    model_config = tmp_path / "config.json"
    _write_moe_config(model_config)
    arguments = [
        "analyze",
        str(model_config),
        "--hardware",
        "generic-discrete-16gib",
        "--backend",
        "vllm",
        "--parameter-count",
        "50000000",
        "--context",
        "4096",
    ]

    assert main(arguments) == 2
    error = capsys.readouterr().err
    assert "active_parameter_count must not exceed total parameters" in error
    assert "Traceback" not in error


def test_non_moe_report_has_no_moe_analysis(capsys) -> None:
    arguments = [
        "analyze",
        "qwen-example",
        "--hardware",
        "generic-discrete-16gib",
        "--backend",
        "vllm",
        "--parameter-count",
        "1000000000",
        "--context",
        "4096",
        "--format",
        "json",
    ]

    assert main(arguments) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["moe_weight_analysis"] is None
