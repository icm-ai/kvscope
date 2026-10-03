"""Behavioral tests for static workload sensitivity sweeps."""

import json

import pytest

from kvscope.api import (
    DeploymentTarget,
    InferenceConfig,
    KVDType,
    WeightDType,
    WorkloadSweepDimension,
    resolve_model,
    sweep_workload,
)
from kvscope.cli.app import main
from kvscope.domain.model_source import ResolvedModel
from kvscope.registries.backends import get_default_backend_registry
from kvscope.registries.hardware import get_default_hardware_registry
from kvscope.serialization.sweep import (
    format_workload_sweep_terminal,
    serialize_workload_sweep_json,
    serialize_workload_sweep_markdown,
)


def _sweep_inputs() -> tuple[ResolvedModel, InferenceConfig, list[DeploymentTarget]]:
    model = resolve_model("qwen-example")
    model = model.model_copy(
        update={
            "spec": model.spec.model_copy(
                update={"parameter_count": 4_000_000_000}
            )
        }
    )
    config = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=4096,
        batch_size=1,
        max_num_seqs=1,
        graph_capture_enabled=False,
    )
    hardware_registry = get_default_hardware_registry()
    backend_registry = get_default_backend_registry()
    hardware = hardware_registry.get("generic-discrete-16gib")
    backend = backend_registry.get("vllm")
    assert hardware is not None
    assert backend is not None
    targets = [
        DeploymentTarget(
            target_id="16gib-vllm",
            hardware=hardware,
            backend=backend,
        ),
        DeploymentTarget(
            target_id="16gib-vllm-second",
            hardware=hardware,
            backend=backend,
        ),
    ]
    return model, config, targets


def test_sweep_context_values_preserve_order_and_other_workload_settings() -> None:
    model, config, targets = _sweep_inputs()

    result = sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
        values=[2048, 4096, 8192],
    )

    assert [point.value for point in result.points] == [2048, 4096, 8192]
    assert [
        point.comparison.inference_config.context_length for point in result.points
    ] == [2048, 4096, 8192]
    assert all(
        len(point.comparison.targets) == 2
        and point.comparison.inference_config.batch_size == 1
        for point in result.points
    )
    requirements = [
        point.comparison.targets[0].report.aggregation.total_requirement.expected_bytes
        for point in result.points
    ]
    assert requirements[0] < requirements[1] < requirements[2]


def test_sweep_active_sequences_changes_only_that_dimension() -> None:
    model, config, targets = _sweep_inputs()

    result = sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.ACTIVE_SEQUENCES,
        values=[1, 2, 4],
    )

    assert [
        point.comparison.inference_config.active_sequences for point in result.points
    ] == [1, 2, 4]
    assert all(
        point.comparison.inference_config.context_length == 4096
        for point in result.points
    )
    requirements = [
        point.comparison.targets[0].report.aggregation.total_requirement.expected_bytes
        for point in result.points
    ]
    assert requirements[0] < requirements[1] < requirements[2]


def test_sweep_reports_observed_status_changes_between_adjacent_samples() -> None:
    model, config, targets = _sweep_inputs()
    hardware_registry = get_default_hardware_registry()
    small_hardware = hardware_registry.get("generic-discrete-8gib")
    assert small_hardware is not None
    targets = [
        DeploymentTarget(
            target_id="8gib-vllm",
            hardware=small_hardware,
            backend=targets[0].backend,
        ),
        DeploymentTarget(
            target_id="16gib-vllm",
            hardware=targets[0].hardware,
            backend=targets[0].backend,
        ),
    ]

    result = sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
        values=[16384, 1024, 32768],
    )

    assert [
        (transition.target_id, transition.from_value, transition.to_value)
        for transition in result.transitions
    ] == [("16gib-vllm", 16384, 1024), ("16gib-vllm", 1024, 32768)]
    assert [
        (transition.from_status.value, transition.to_status.value)
        for transition in result.transitions
    ] == [("tight", "feasible"), ("feasible", "tight")]
    terminal = format_workload_sweep_terminal(result)
    markdown = serialize_workload_sweep_markdown(result)
    serialized = json.loads(serialize_workload_sweep_json(result))
    assert serialized["transitions"][0]["from_value"] == 16384
    assert serialized["transitions"][0]["to_value"] == 1024
    assert "16384 -> 1024 (tight -> feasible)" in terminal
    assert "| `16gib-vllm` | 16384 | 1024 | tight | feasible |" in markdown
    assert "exact boundaries are unknown" in markdown


def test_sweep_requires_multiple_unique_positive_values() -> None:
    model, config, targets = _sweep_inputs()

    with pytest.raises(ValueError, match="at least two"):
        sweep_workload(
            model=model,
            inference_config=config,
            targets=targets,
            dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
            values=[4096],
        )
    with pytest.raises(ValueError, match="unique"):
        sweep_workload(
            model=model,
            inference_config=config,
            targets=targets,
            dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
            values=[4096, 4096],
        )
    with pytest.raises(ValueError, match="positive"):
        sweep_workload(
            model=model,
            inference_config=config,
            targets=targets,
            dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
            values=[0, 4096],
        )


def test_sweep_cli_emits_versioned_scenario_report(capsys) -> None:
    arguments = [
        "sweep",
        "qwen-example",
        "--target",
        "generic-discrete-16gib=vllm",
        "--parameter-count",
        "4000000000",
        "--contexts",
        "2048",
        "4096",
        "--format",
        "json",
    ]

    assert main(arguments) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["kind"] == "workload_sweep"
    assert output["schema_version"] == "v0.1"
    assert output["dimension"] == "context_length"
    assert [point["value"] for point in output["points"]] == [2048, 4096]
    assert all(len(point["comparison"]["targets"]) == 1 for point in output["points"])
    assert output["transitions"] == []
    assert all(
        point["comparison"]["kind"] == "deployment_comparison"
        for point in output["points"]
    )

    assert main([*arguments[:-1], "terminal"]) == 0
    assert "context_length=2048" in capsys.readouterr().out
    assert main([*arguments[:-1], "markdown"]) == 0
    assert "| context_length | Target |" in capsys.readouterr().out


def test_sweep_cli_handles_invalid_inference_configuration(capsys) -> None:
    arguments = [
        "sweep",
        "qwen-example",
        "--target",
        "generic-discrete-16gib=vllm",
        "--parameter-count",
        "4000000000",
        "--contexts",
        "-1",
        "4096",
    ]

    assert main(arguments) == 2
    error = capsys.readouterr().err
    assert "context_length" in error
    assert "Traceback" not in error


def test_sweep_cli_accepts_active_sequence_scenarios(capsys) -> None:
    arguments = [
        "sweep",
        "qwen-example",
        "--target",
        "generic-discrete-16gib=vllm",
        "--parameter-count",
        "4000000000",
        "--context",
        "4096",
        "--active-sequences",
        "1",
        "4",
        "--format",
        "json",
    ]

    assert main(arguments) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["dimension"] == "active_sequences"
    assert [point["value"] for point in output["points"]] == [1, 4]
    assert [
        point["comparison"]["targets"][0]["report"]["provenance"][
            "inference_config"
        ]["active_sequences"]
        for point in output["points"]
    ] == [1, 4]
