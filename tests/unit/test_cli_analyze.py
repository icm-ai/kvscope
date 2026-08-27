"""End-to-end tests for the ``kvscope analyze`` CLI command."""

import json

from kvscope.cli.app import main

ANALYZE_ARGUMENTS = [
    "analyze",
    "qwen-example",
    "--hardware",
    "generic-discrete-16gib",
    "--backend",
    "vllm",
    "--parameter-count",
    "4000000000",
    "--context",
    "4096",
]


def test_analyze_runs_the_complete_assessment_workflow(capsys) -> None:
    """A model, backend, and hardware ID should produce a feasibility report."""
    assert main(ANALYZE_ARGUMENTS) == 0

    output = capsys.readouterr().out
    assert "KVScope Memory Feasibility Report" in output
    assert "Resident Weights" in output
    assert "Unverified generic profile" in output


def test_analyze_json_includes_calibration_provenance(capsys) -> None:
    """A feasibility JSON report carries identity needed for calibration checks."""
    assert main([*ANALYZE_ARGUMENTS, "--format", "json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["provenance"]["model_id"] == "qwen-example"
    assert output["provenance"]["backend_profile_id"] == "vllm-generic-unverified-v0"
    assert output["provenance"]["inference_config"]["context_length"] == 4096


def test_analyze_can_include_recommendations_as_json(capsys) -> None:
    """Recommendation output should contain the baseline assessment JSON."""
    assert main([*ANALYZE_ARGUMENTS, "--recommend", "--format", "json"]) == 0

    output = capsys.readouterr().out
    assert '"kind": "recommendation_report"' in output
    assert '"baseline_report"' in output


def test_analyze_requires_parameter_count_when_model_does_not_provide_one(
    capsys,
) -> None:
    """Incomplete model metadata must not silently produce a weight estimate."""
    arguments = [
        "analyze",
        "qwen-example",
        "--hardware",
        "generic-discrete-16gib",
        "--backend",
        "vllm",
        "--context",
        "4096",
    ]

    assert main(arguments) == 2
    assert "pass --parameter-count" in capsys.readouterr().err
