"""Schema and negative tests for the Phase 1 domain boundary."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kvscope.domain.backend import BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.constraint import Constraint
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import (
    Confidence,
    FeasibilityStatus,
    MemoryTopology,
    RiskLevel,
)
from kvscope.domain.estimate import EstimateComponent, MemoryEstimate
from kvscope.domain.evidence import Evidence
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.hardware import HardwareSpec
from kvscope.domain.model import ModelSpec
from kvscope.domain.recommendation import Recommendation
from kvscope.domain.report import AnalysisReport


def model() -> ModelSpec:
    return ModelSpec(
        model_id="example/model",
        architecture="example",
        num_hidden_layers=24,
        hidden_size=4096,
        num_attention_heads=32,
        num_key_value_heads=8,
        head_dim=128,
        source="manual",
    )


def hardware() -> HardwareSpec:
    return HardwareSpec(
        hardware_id="example-device",
        vendor="example",
        device_family="gpu",
        name="Example Device",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory_bytes=16 * 1024**3,
        default_system_reserve_bytes=512 * 1024**2,
        supported_backends=["example-backend"],
    )


def backend() -> BackendSpec:
    return BackendSpec(
        backend_id="example-backend",
        base_overhead_bytes=128 * 1024**2,
        overhead_per_billion_parameters_bytes=64 * 1024**2,
        graph_capture_reserve_bytes=32 * 1024**2,
        workspace_ratio=0.1,
        allocator_margin_ratio=0.05,
        kv_block_size=16,
        supports_kv_dtypes=[KVDType.FP16, KVDType.INT8],
        supports_cpu_offload=True,
        confidence=Confidence.MEDIUM,
        evidence_ids=["backend-docs"],
    )


def component(name: str, value: int) -> EstimateComponent:
    return EstimateComponent(
        name=name,
        bytes=value,
        confidence=Confidence.EXACT,
        formula=None,
    )


def estimate() -> MemoryEstimate:
    return MemoryEstimate(
        weights=component("weights", 100),
        kv_cache=component("kv_cache", 200),
        runtime_overhead=component("runtime_overhead", 300),
        graph_capture=component("graph_capture", 400),
        workspace=component("workspace", 500),
        system_reserve=component("system_reserve", 600),
        safety_margin=component("safety_margin", 700),
        total=component("total", 2800),
    )


def test_hardware_backend_and_inference_schemas_validate_domain_values() -> None:
    config = InferenceConfig(
        weight_dtype=WeightDType.INT4,
        kv_dtype=KVDType.FP16,
        context_length=4096,
        batch_size=2,
        max_num_seqs=4,
        cpu_offload_bytes=1024,
    )

    assert hardware().memory_topology is MemoryTopology.DISCRETE
    assert backend().supports_kv_dtypes == [KVDType.FP16, KVDType.INT8]
    assert config.active_sequences == 4
    assert config.graph_capture_enabled is True


@pytest.mark.parametrize(
    ("model_type", "data"),
    [
        (HardwareSpec, {"total_memory_bytes": -1}),
        (BackendSpec, {"workspace_ratio": 1.1}),
        (InferenceConfig, {"context_length": 0}),
    ],
)
def test_schemas_reject_invalid_positive_or_ratio_values(model_type, data) -> None:
    factories = {
        HardwareSpec: hardware,
        BackendSpec: backend,
        InferenceConfig: lambda: InferenceConfig(
            weight_dtype=WeightDType.FP16,
            kv_dtype=KVDType.FP16,
            context_length=1,
        ),
    }
    value = factories[model_type]()
    payload = value.model_dump()
    payload.update(data)

    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


def test_hardware_rejects_reserve_larger_than_total_memory() -> None:
    payload = hardware().model_dump()
    payload["default_system_reserve_bytes"] = payload["total_memory_bytes"] + 1

    with pytest.raises(ValidationError, match="must not exceed"):
        HardwareSpec.model_validate(payload)


def test_feasibility_rejects_inconsistent_headroom() -> None:
    with pytest.raises(ValidationError, match="headroom_bytes"):
        FeasibilityResult(
            status=FeasibilityStatus.FEASIBLE,
            risk=RiskLevel.LOW,
            required_bytes=100,
            available_bytes=200,
            headroom_bytes=50,
        )


def test_estimate_component_rejects_inverted_or_out_of_range_bounds() -> None:
    with pytest.raises(ValidationError, match="upper_bound_bytes"):
        EstimateComponent(
            name="weights",
            bytes=100,
            lower_bound_bytes=200,
            upper_bound_bytes=150,
            confidence=Confidence.MEDIUM,
        )

    with pytest.raises(ValidationError, match="within estimate bounds"):
        EstimateComponent(
            name="weights",
            bytes=100,
            lower_bound_bytes=101,
            confidence=Confidence.MEDIUM,
        )


def test_report_composes_all_phase_one_schemas() -> None:
    report = AnalysisReport(
        schema_version="0.1",
        generated_at=datetime.now(UTC),
        model=model(),
        hardware=hardware(),
        backend=backend(),
        config=InferenceConfig(
            weight_dtype=WeightDType.INT4,
            kv_dtype=KVDType.FP16,
            context_length=4096,
        ),
        estimate=estimate(),
        feasibility=FeasibilityResult(
            status=FeasibilityStatus.FEASIBLE,
            risk=RiskLevel.LOW,
            required_bytes=2800,
            available_bytes=4000,
            headroom_bytes=1200,
            headroom_ratio=0.42857142857142855,
        ),
        constraints=[
            Constraint(
                code="KV_CACHE_EXCEEDS_BUDGET",
                title="KV cache exceeds budget",
                severity="high",
                component="kv_cache",
                current_value=200,
                threshold=100,
                explanation="The requested KV cache is larger than the budget.",
            )
        ],
        recommendations=[
            Recommendation(
                recommendation_id="reduce-context",
                title="Reduce context length",
                explanation="This lowers KV cache demand.",
                parameter="context_length",
                current_value=4096,
                suggested_value=2048,
                priority=100,
            )
        ],
        evidence=[
            Evidence(
                evidence_id="backend-docs",
                source_type="official_documentation",
                source="Example backend documentation",
            )
        ],
    )

    dumped = report.model_dump(mode="json")
    assert dumped["feasibility"]["status"] == "feasible"
    assert dumped["config"]["weight_dtype"] == "int4"
    assert report.model_config["frozen"] is True


def test_all_domain_enums_have_stable_wire_values() -> None:
    assert {item.value for item in WeightDType} == {
        "fp32",
        "fp16",
        "bf16",
        "fp8",
        "int8",
        "int4",
    }
    assert {item.value for item in KVDType} == {
        "fp32",
        "fp16",
        "bf16",
        "fp8",
        "int8",
    }
    assert {item.value for item in MemoryTopology} == {
        "discrete",
        "unified",
        "system",
    }
    assert {item.value for item in Confidence} == {
        "exact",
        "high",
        "medium",
        "low",
        "unknown",
    }
    assert {item.value for item in FeasibilityStatus} == {
        "feasible",
        "tight",
        "infeasible",
        "unknown",
    }
    assert {item.value for item in RiskLevel} == {
        "low",
        "medium",
        "high",
        "unknown",
    }


def test_domain_model_validates_raw_dicts_with_string_enums() -> None:
    hw_dict = {
        "hardware_id": "test-device",
        "vendor": "test-vendor",
        "device_family": "gpu",
        "name": "Test Device",
        "memory_topology": "discrete",
        "total_memory_bytes": 16 * 1024**3,
        "default_system_reserve_bytes": 512 * 1024**2,
    }
    parsed_hw = HardwareSpec.model_validate(hw_dict)
    assert parsed_hw.memory_topology is MemoryTopology.DISCRETE

    backend_dict = {
        "backend_id": "vllm",
        "base_overhead_bytes": 0,
        "overhead_per_billion_parameters_bytes": 0,
        "graph_capture_reserve_bytes": 0,
        "workspace_ratio": 0.0,
        "allocator_margin_ratio": 0.0,
        "supports_kv_dtypes": ["fp16", "int8"],
        "supports_cpu_offload": False,
        "confidence": "exact",
    }
    parsed_backend = BackendSpec.model_validate(backend_dict)
    assert parsed_backend.supports_kv_dtypes == [KVDType.FP16, KVDType.INT8]
    assert parsed_backend.confidence is Confidence.EXACT


def test_inference_config_traces_active_sequences_source() -> None:
    cfg1 = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=100,
        batch_size=8,
        max_num_seqs=1,
    )
    assert cfg1.active_sequences == 8
    assert cfg1.active_sequences_source == "batch_size"

    cfg2 = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=100,
        batch_size=1,
        max_num_seqs=16,
    )
    assert cfg2.active_sequences == 16
    assert cfg2.active_sequences_source == "max_num_seqs"

    cfg3 = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=100,
        batch_size=4,
        max_num_seqs=4,
    )
    assert cfg3.active_sequences == 4
    assert cfg3.active_sequences_source == "equal"

