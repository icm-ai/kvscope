"""Behavioral tests for the multi-target static comparison interface."""

import json

import pytest

from kvscope.api import DeploymentTarget, compare_deployment_targets, resolve_model
from kvscope.cli.app import main
from kvscope.domain.config import InferenceConfig
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.model_source import ResolvedModel
from kvscope.registries.backends import get_default_backend_registry
from kvscope.registries.hardware import get_default_hardware_registry


def _comparison_inputs() -> tuple[
    ResolvedModel, InferenceConfig, list[DeploymentTarget]
]:
    model = resolve_model("qwen-example")
    model = model.model_copy(
        update={
            "spec": model.spec.model_copy(update={"parameter_count": 4_000_000_000})
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
    backend = backend_registry.get("vllm")
    assert backend is not None
    small_hardware = hardware_registry.get("generic-discrete-8gib")
    large_hardware = hardware_registry.get("generic-discrete-16gib")
    assert small_hardware is not None
    assert large_hardware is not None
    targets = [
        DeploymentTarget(
            target_id="small-gpu",
            hardware=small_hardware,
            backend=backend,
        ),
        DeploymentTarget(
            target_id="large-gpu",
            hardware=large_hardware,
            backend=backend,
        ),
    ]
    return model, config, targets


def test_comparison_evaluates_each_explicit_target_with_shared_workload() -> None:
    model, config, targets = _comparison_inputs()

    result = compare_deployment_targets(
        model=model,
        inference_config=config,
        targets=targets,
    )

    assert [target.target_id for target in result.targets] == [
        "small-gpu",
        "large-gpu",
    ]
    assert [
        target.report.provenance.hardware_profile_id
        for target in result.targets
    ] == ["generic-discrete-8gib", "generic-discrete-16gib"]
    assert all(
        target.report.provenance.inference_config.context_length == 4096
        for target in result.targets
    )
    assert (
        result.targets[0].report.feasibility.product_status.value
        == "infeasible"
    )
    assert (
        result.targets[1].report.feasibility.product_status.value
        in {"feasible", "tight"}
    )


def test_compare_cli_outputs_same_workload_for_multiple_targets(capsys) -> None:
    arguments = [
        "compare",
        "qwen-example",
        "--target",
        "generic-discrete-8gib=vllm",
        "--target",
        "generic-discrete-16gib=vllm",
        "--backend-version",
        "0.6.6",
        "--parameter-count",
        "4000000000",
        "--context",
        "4096",
        "--format",
        "json",
    ]

    assert main(arguments) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["kind"] == "deployment_comparison"
    assert output["inference_config"]["context_length"] == 4096
    assert output["parameter_count"] == 4_000_000_000
    assert [
        target["hardware_profile_id"] for target in output["targets"]
    ] == ["generic-discrete-8gib", "generic-discrete-16gib"]
    assert all(target["backend_version"] == "0.6.6" for target in output["targets"])

    assert main([*arguments[:-1], "markdown"]) == 0
    markdown = capsys.readouterr().out
    assert (
        "| Target | Hardware | Backend (version) | Feasibility | Confidence |"
        in markdown
    )
    assert "vllm-generic-unverified-v0" in markdown
    assert "(0.6.6)" in markdown


def test_compare_cli_reports_backend_workload_mismatch_without_traceback(
    capsys,
) -> None:
    arguments = [
        "compare",
        "qwen-example",
        "--target",
        "generic-discrete-16gib=vllm",
        "--target",
        "generic-discrete-16gib=llama.cpp",
        "--parameter-count",
        "4000000000",
        "--context",
        "4096",
        "--graph-capture",
    ]

    assert main(arguments) == 2
    assert "does not support graph capture" in capsys.readouterr().err


def test_compare_cli_handles_invalid_inference_configuration(capsys) -> None:
    arguments = [
        "compare",
        "qwen-example",
        "--target",
        "generic-discrete-8gib=vllm",
        "--target",
        "generic-discrete-16gib=vllm",
        "--parameter-count",
        "4000000000",
        "--context",
        "-1",
    ]

    assert main(arguments) == 2
    error = capsys.readouterr().err
    assert "context_length" in error
    assert "Traceback" not in error


def test_comparison_can_vary_backend_on_the_same_hardware() -> None:
    model, config, targets = _comparison_inputs()
    llama_cpp = get_default_backend_registry().get("llama.cpp")
    assert llama_cpp is not None
    targets = [
        DeploymentTarget(
            target_id="16gib-vllm",
            hardware=targets[1].hardware,
            backend=targets[1].backend,
        ),
        DeploymentTarget(
            target_id="16gib-llama-cpp",
            hardware=targets[1].hardware,
            backend=llama_cpp,
        ),
    ]

    result = compare_deployment_targets(
        model=model,
        inference_config=config,
        targets=targets,
    )

    assert [target.backend_profile_id for target in result.targets] == [
        "vllm-generic-unverified-v0",
        "llama-cpp-generic-unverified-v0",
    ]
    assert all(
        target.hardware_profile_id == "generic-discrete-16gib"
        for target in result.targets
    )


def test_comparison_requires_at_least_two_unique_targets() -> None:
    model, config, targets = _comparison_inputs()

    with pytest.raises(ValueError, match="at least two"):
        compare_deployment_targets(
            model=model,
            inference_config=config,
            targets=targets[:1],
        )

    with pytest.raises(ValueError, match="must be unique"):
        compare_deployment_targets(
            model=model,
            inference_config=config,
            targets=[targets[0], targets[0]],
        )
