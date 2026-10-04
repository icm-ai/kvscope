"""Contracts for shared static workload and target orchestration."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from kvscope.api import (
    InferenceConfig,
    KVDType,
    WeightDType,
    WorkloadSweepDimension,
    compare_deployment_targets,
    resolve_model,
    sweep_workload,
)
from kvscope.calibration import load_memory_feasibility_report
from kvscope.cli.app import main
from kvscope.domain.comparison import DeploymentTarget as Target
from kvscope.engines import candidate_evaluation, static_analysis
from kvscope.errors import InvalidModelConfigError
from kvscope.registries.backends import get_default_backend_registry
from kvscope.registries.hardware import get_default_hardware_registry


def _inputs(
    *,
    hardware_id: str = "generic-discrete-16gib",
    weight_dtype: WeightDType = WeightDType.FP16,
    kv_dtype: KVDType = KVDType.FP16,
    context_length: int = 4096,
    batch_size: int = 1,
    max_num_seqs: int = 1,
    prefix_tokens: int = 0,
    multimodal_tokens: int = 0,
    graph_capture_enabled: bool = False,
    active_sequences_override: int | None = None,
) -> tuple:
    resolved = resolve_model("qwen-example")
    resolved = resolved.model_copy(
        update={
            "spec": resolved.spec.model_copy(update={"parameter_count": 4_000_000_000})
        }
    )
    config = InferenceConfig(
        weight_dtype=weight_dtype,
        kv_dtype=kv_dtype,
        context_length=context_length,
        batch_size=batch_size,
        max_num_seqs=max_num_seqs,
        prefix_tokens=prefix_tokens,
        multimodal_tokens=multimodal_tokens,
        graph_capture_enabled=graph_capture_enabled,
        active_sequences_override=active_sequences_override,
    )
    hardware_registry = get_default_hardware_registry()
    backend_registry = get_default_backend_registry()
    hardware = hardware_registry.get(hardware_id)
    backend = backend_registry.get("vllm")
    assert hardware is not None
    assert backend is not None
    targets = [
        Target(
            target_id=f"first-{hardware_id}",
            hardware=hardware,
            backend=backend,
            backend_version="0.6.6",
        ),
        Target(
            target_id=f"second-{hardware_id}",
            hardware=hardware,
            backend=backend,
            backend_version="0.6.6",
        ),
    ]
    return resolved, config, targets


def _analyze_report(
    capsys,
    *,
    hardware_id: str,
    weight_dtype: WeightDType,
    kv_dtype: KVDType,
    context_length: int,
    batch_size: int,
    max_num_seqs: int,
    prefix_tokens: int,
    multimodal_tokens: int,
    graph_capture_enabled: bool,
    user_reserve_bytes: int,
) -> dict:
    args = [
        "analyze",
        "qwen-example",
        "--hardware",
        hardware_id,
        "--backend",
        "vllm",
        "--backend-version",
        "0.6.6",
        "--parameter-count",
        "4000000000",
        "--context",
        str(context_length),
        "--batch-size",
        str(batch_size),
        "--max-num-seqs",
        str(max_num_seqs),
        "--prefix-tokens",
        str(prefix_tokens),
        "--multimodal-tokens",
        str(multimodal_tokens),
        "--weight-dtype",
        weight_dtype.value,
        "--kv-dtype",
        kv_dtype.value,
        "--user-reserve-bytes",
        str(user_reserve_bytes),
        "--format",
        "json",
    ]
    if graph_capture_enabled:
        args.append("--graph-capture")
    # CLI baseline checks intentionally observe its public serialized report.
    assert main(args) == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    (
        "hardware_id",
        "weight_dtype",
        "kv_dtype",
        "graph",
        "reserve",
        "batch",
        "max_seqs",
    ),
    [
        ("generic-discrete-16gib", WeightDType.FP16, KVDType.FP16, False, 0, 1, 1),
        ("generic-discrete-8gib", WeightDType.INT4, KVDType.FP16, True, 1234567, 2, 1),
        ("generic-unified-16gib", WeightDType.FP8, KVDType.FP8, False, 987654, 1, 4),
        ("generic-unified-32gib", WeightDType.INT8, KVDType.FP16, True, 0, 4, 2),
    ],
)
def test_analyze_cli_report_matches_compare_target_report(
    capsys,
    hardware_id: str,
    weight_dtype: WeightDType,
    kv_dtype: KVDType,
    graph: bool,
    reserve: int,
    batch: int,
    max_seqs: int,
) -> None:
    args = dict(
        hardware_id=hardware_id,
        weight_dtype=weight_dtype,
        kv_dtype=kv_dtype,
        context_length=4096,
        batch_size=batch,
        max_num_seqs=max_seqs,
        prefix_tokens=13,
        multimodal_tokens=29,
        graph_capture_enabled=graph,
        user_reserve_bytes=reserve,
    )
    analyze_report = _analyze_report(capsys, **args)
    model, config, targets = _inputs(
        hardware_id=hardware_id,
        weight_dtype=weight_dtype,
        kv_dtype=kv_dtype,
        context_length=4096,
        batch_size=batch,
        max_num_seqs=max_seqs,
        prefix_tokens=13,
        multimodal_tokens=29,
        graph_capture_enabled=graph,
    )
    comparison = compare_deployment_targets(
        model=model,
        inference_config=config,
        targets=targets,
        user_reserve_bytes=reserve,
    )
    compare_report = comparison.targets[0].report.model_dump(mode="json")
    analyze_report.pop("kind")
    assert analyze_report == compare_report
    assert analyze_report["provenance"]["inference_config"]["prefix_tokens"] == 13
    assert analyze_report["provenance"]["inference_config"]["multimodal_tokens"] == 29


def test_context_sweep_points_match_python_compare_and_preserve_input_order() -> None:
    model, config, targets = _inputs(batch_size=2, max_num_seqs=4)
    values = [8192, 1024, 4096]
    sweep = sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
        values=values,
    )
    assert [point.value for point in sweep.points] == values
    for point in sweep.points:
        point_config = config.model_copy(update={"context_length": point.value})
        compared = compare_deployment_targets(
            model=model, inference_config=point_config, targets=targets
        )
        point_reports = [
            target.report.model_dump(mode="json") for target in point.comparison.targets
        ]
        compared_reports = [
            target.report.model_dump(mode="json") for target in compared.targets
        ]
        assert point_reports == compared_reports


def test_active_sequence_sweep_matches_compare_without_rewriting_base_config() -> None:
    model, config, targets = _inputs(batch_size=2, max_num_seqs=4)
    original = config.model_dump(mode="json")
    values = [4, 1, 3]
    sweep = sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.ACTIVE_SEQUENCES,
        values=values,
    )
    assert config.model_dump(mode="json") == original
    assert [point.value for point in sweep.points] == values
    for point in sweep.points:
        point_config = config.model_copy(
            update={"active_sequences_override": point.value}
        )
        compared = compare_deployment_targets(
            model=model, inference_config=point_config, targets=targets
        )
        point_reports = [
            target.report.model_dump(mode="json") for target in point.comparison.targets
        ]
        compared_reports = [
            target.report.model_dump(mode="json") for target in compared.targets
        ]
        assert point_reports == compared_reports
        provenance = point.comparison.targets[0].report.provenance.inference_config
        assert (provenance.batch_size, provenance.max_num_seqs) == (2, 4)


@pytest.mark.parametrize("values", [[True, 2], [1, 2.0], [1], [1, 1], [0, 1]])
def test_sweep_rejects_invalid_samples(values: list[object]) -> None:
    model, config, targets = _inputs()
    with pytest.raises(ValueError):
        sweep_workload(
            model=model,
            inference_config=config,
            targets=targets,
            dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
            values=values,
        )


def test_comparison_and_sweep_do_not_mutate_model_or_targets() -> None:
    model, config, targets = _inputs()
    snapshots = (
        model.model_dump(mode="json"),
        config.model_dump(mode="json"),
        [target.model_dump(mode="json") for target in targets],
    )
    compare_deployment_targets(
        model=model, inference_config=config, targets=targets, user_reserve_bytes=11
    )
    sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
        values=[2048, 4096],
        user_reserve_bytes=13,
    )
    assert snapshots == (
        model.model_dump(mode="json"),
        config.model_dump(mode="json"),
        [target.model_dump(mode="json") for target in targets],
    )


def test_weight_estimate_once_for_analyze_compare_and_each_sweep_sample(
    monkeypatch, capsys
) -> None:
    model, config, targets = _inputs()
    actual = static_analysis.estimate_weight_memory
    weight_spy = Mock(wraps=actual)
    monkeypatch.setattr(static_analysis, "estimate_weight_memory", weight_spy)
    kv_actual = static_analysis.estimate_kv_cache
    kv_spy = Mock(wraps=kv_actual)
    monkeypatch.setattr(static_analysis, "estimate_kv_cache", kv_spy)
    budget_actual = static_analysis.estimate_hardware_memory_budget
    budget_spy = Mock(wraps=budget_actual)
    monkeypatch.setattr(static_analysis, "estimate_hardware_memory_budget", budget_spy)
    runtime_actual = static_analysis.estimate_runtime_overhead
    runtime_spy = Mock(wraps=runtime_actual)
    monkeypatch.setattr(static_analysis, "estimate_runtime_overhead", runtime_spy)

    assert (
        main(
            [
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
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    actual_counts = (
        weight_spy.call_count,
        kv_spy.call_count,
        budget_spy.call_count,
        runtime_spy.call_count,
    )
    assert actual_counts == (1, 1, 1, 1)
    weight_spy.reset_mock()
    kv_spy.reset_mock()
    budget_spy.reset_mock()
    runtime_spy.reset_mock()

    compare_deployment_targets(
        model=model,
        inference_config=config,
        targets=targets,
        user_reserve_bytes=12345,
    )
    actual_counts = (
        weight_spy.call_count,
        kv_spy.call_count,
        budget_spy.call_count,
        runtime_spy.call_count,
    )
    assert actual_counts == (1, 2, 2, 2)
    assert all(
        call.kwargs["user_reserve_bytes"] == 12345 for call in budget_spy.call_args_list
    )
    weight_spy.reset_mock()
    kv_spy.reset_mock()
    budget_spy.reset_mock()
    runtime_spy.reset_mock()

    sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
        values=[8192, 1024, 4096],
    )
    actual_counts = (
        weight_spy.call_count,
        kv_spy.call_count,
        budget_spy.call_count,
        runtime_spy.call_count,
    )
    assert actual_counts == (3, 6, 6, 6)


def test_moe_preparation_and_provenance_projection_are_once_per_workload(
    monkeypatch,
) -> None:
    model, config, targets = _inputs()
    model = model.model_copy(
        update={
            "spec": model.spec.model_copy(
                update={
                    "active_parameter_count": 100_000_000,
                    "num_experts": 8,
                    "num_experts_per_tok": 2,
                }
            )
        }
    )
    moe_actual = static_analysis.analyze_moe_weight_structure
    moe_spy = Mock(wraps=moe_actual)
    monkeypatch.setattr(static_analysis, "analyze_moe_weight_structure", moe_spy)
    projection_actual = static_analysis.project_inference_config
    projection_spy = Mock(wraps=projection_actual)
    monkeypatch.setattr(static_analysis, "project_inference_config", projection_spy)

    comparison = compare_deployment_targets(
        model=model, inference_config=config, targets=targets
    )
    assert moe_spy.call_count == 1
    assert projection_spy.call_count == 1
    assert all(
        target.report.moe_weight_analysis.active_parameter_count == 100_000_000
        for target in comparison.targets
    )
    assert all(
        target.report.aggregation.resident_weights.memory.expected_bytes
        == 8_000_000_000
        for target in comparison.targets
    )
    moe_spy.reset_mock()
    projection_spy.reset_mock()
    sweep = sweep_workload(
        model=model,
        inference_config=config,
        targets=targets,
        dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
        values=[8192, 1024],
    )
    assert moe_spy.call_count == 2
    assert projection_spy.call_count == 2
    assert all(
        point.comparison.targets[0].report.moe_weight_analysis.active_parameter_count
        == 100_000_000
        for point in sweep.points
    )


def test_analyze_recommendation_does_not_recompute_baseline_weight(
    monkeypatch, capsys
) -> None:
    actual = static_analysis.estimate_weight_memory
    weight_spy = Mock(wraps=actual)
    monkeypatch.setattr(static_analysis, "estimate_weight_memory", weight_spy)
    candidate_actual = candidate_evaluation.estimate_weight_memory
    candidate_spy = Mock(wraps=candidate_actual)
    monkeypatch.setattr(candidate_evaluation, "estimate_weight_memory", candidate_spy)
    assert (
        main(
            [
                "analyze",
                "qwen-example",
                "--hardware",
                "generic-discrete-8gib",
                "--backend",
                "vllm",
                "--parameter-count",
                "4000000000",
                "--context",
                "32768",
                "--recommend",
                "--format",
                "json",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["kind"] == "recommendation_report"
    assert "aggregation" in output["baseline_report"]
    assert output["primary_recommendation"]["action"] == "change_weight_dtype"
    assert weight_spy.call_count == 1
    assert candidate_spy.call_count == 1


def test_analyze_json_remains_loadable_for_calibration_identity(
    tmp_path, capsys
) -> None:
    args = [
        "analyze",
        "qwen-example",
        "--hardware",
        "generic-discrete-16gib",
        "--backend",
        "vllm",
        "--backend-version",
        "0.6.6",
        "--parameter-count",
        "4000000000",
        "--context",
        "4096",
        "--batch-size",
        "2",
        "--max-num-seqs",
        "4",
        "--prefix-tokens",
        "11",
        "--multimodal-tokens",
        "17",
        "--weight-dtype",
        "int4",
        "--kv-dtype",
        "fp16",
        "--graph-capture",
        "--format",
        "json",
    ]
    assert main(args) == 0
    path = tmp_path / "report.json"
    path.write_text(capsys.readouterr().out, encoding="utf-8")
    loaded = load_memory_feasibility_report(path)
    provenance = loaded.provenance
    assert provenance is not None
    assert (provenance.model_id, provenance.model_revision) == (
        "qwen-example",
        "immutable-example-revision",
    )
    assert provenance.model_config_digest == (
        "68e3ec5480e423ac92e15ceef26901953a9fa82f83540730f1c1f9cc71661afa"
    )
    assert (provenance.backend_profile_id, provenance.backend_version) == (
        "vllm-generic-unverified-v0",
        "0.6.6",
    )
    assert provenance.hardware_profile_id == "generic-discrete-16gib"
    config = provenance.inference_config.model_dump(mode="json")
    assert len(config) == 10
    assert config == {
        "context_length": 4096,
        "batch_size": 2,
        "max_num_seqs": 4,
        "active_sequences": 4,
        "prefix_tokens": 11,
        "multimodal_tokens": 17,
        "weight_dtype": "int4",
        "kv_dtype": "fp16",
        "graph_capture_enabled": True,
        "cpu_offload_bytes": 0,
    }


def test_analyze_recommendation_preserves_no_change_case(capsys) -> None:
    assert (
        main(
            [
                "analyze",
                "qwen-example",
                "--hardware",
                "generic-discrete-16gib",
                "--backend",
                "vllm",
                "--parameter-count",
                "4000000000",
                "--context",
                "1024",
                "--recommend",
                "--format",
                "json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["primary_recommendation"]["action"] == "no_change_required"
    assert report["eligibility"]["eligibility"] == "advisory_only"


def test_analyze_preserves_target_error_priority_over_invalid_moe_override(
    tmp_path,
) -> None:
    model_config = tmp_path / "moe-config.json"
    model_config.write_text(
        json.dumps(
            {
                "model_id": "review-moe",
                "model_type": "llama",
                "num_hidden_layers": 2,
                "hidden_size": 16,
                "num_attention_heads": 4,
                "num_key_value_heads": 2,
                "head_dim": 4,
                "parameter_count": 1000,
                "active_parameter_count": 500,
                "num_experts": 8,
                "num_experts_per_tok": 2,
            }
        ),
        encoding="utf-8",
    )
    source_root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source_root / "src")
    command = [
        sys.executable,
        "-m",
        "kvscope",
        "analyze",
        str(model_config),
        "--offline",
        "--hardware",
        "generic-discrete-16gib",
        "--backend",
        "vllm",
        "--context",
        "4096",
        "--parameter-count",
        "100",
    ]
    for reserve, expected_exit, expected_message in (
        (None, 2, "active_parameter_count must not exceed total parameters"),
        (-1, 1, "user_reserve_bytes must be non-negative"),
    ):
        args = command.copy()
        if reserve is not None:
            args.extend(["--user-reserve-bytes", str(reserve)])
        result = subprocess.run(
            args,
            cwd=source_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == expected_exit
        assert expected_message in result.stderr


def test_comparison_keeps_moe_error_before_target_assessment() -> None:
    model, config, targets = _inputs()
    model = model.model_copy(
        update={
            "spec": model.spec.model_copy(
                update={
                    "parameter_count": 100,
                    "active_parameter_count": 500,
                    "num_experts": 8,
                    "num_experts_per_tok": 2,
                }
            )
        }
    )
    with pytest.raises(ValueError, match="active_parameter_count"):
        compare_deployment_targets(
            model=model,
            inference_config=config,
            targets=targets,
            user_reserve_bytes=-1,
        )


def test_analyze_preserves_unhandled_weight_estimation_error(monkeypatch) -> None:
    monkeypatch.setattr(
        static_analysis,
        "estimate_weight_memory",
        Mock(side_effect=InvalidModelConfigError("invalid weight inputs")),
    )
    with pytest.raises(InvalidModelConfigError, match="invalid weight inputs"):
        main(
            [
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
        )


def test_static_entrypoints_keep_missing_parameter_and_empty_target_errors() -> None:
    model, config, targets = _inputs()
    missing_parameters = resolve_model("qwen-example")
    with pytest.raises(ValueError, match="parameter_count"):
        compare_deployment_targets(
            model=missing_parameters,
            inference_config=config,
            targets=targets,
        )
    with pytest.raises(ValueError, match="parameter_count"):
        sweep_workload(
            model=missing_parameters,
            inference_config=config,
            targets=targets,
            dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
            values=[2048, 4096],
        )
    with pytest.raises(ValueError, match="at least one deployment target"):
        sweep_workload(
            model=model,
            inference_config=config,
            targets=[],
            dimension=WorkloadSweepDimension.CONTEXT_LENGTH,
            values=[2048, 4096],
        )
    with pytest.raises(ValueError, match="supported workload sweep dimension"):
        sweep_workload(
            model=model,
            inference_config=config,
            targets=targets,
            dimension=cast(WorkloadSweepDimension, "unsupported"),
            values=[2048, 4096],
        )


def test_static_workload_preparation_rejects_missing_parameter_count() -> None:
    model = resolve_model("qwen-example")
    with pytest.raises(ValueError, match="parameter_count"):
        static_analysis.prepare_static_workload(
            model,
            InferenceConfig(
                weight_dtype=WeightDType.FP16,
                kv_dtype=KVDType.FP16,
                context_length=4096,
            ),
        )
