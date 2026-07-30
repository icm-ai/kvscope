"""Unit tests for Memory Aggregator engine."""

from fractions import Fraction

import pytest

from kvscope.calculators.kv_cache import KVCacheEstimate, KVCacheFormulaInputs
from kvscope.calculators.weights import WeightEstimationMethod, WeightMemoryEstimate
from kvscope.domain.dtypes import KVDType
from kvscope.domain.enums import Confidence
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.engines.aggregation import (
    _min_confidence,
    aggregate_memory_requirements,
)
from kvscope.errors import MissingMemoryComponentError


def _make_sample_weights(
    resident_bytes: int = 4000, confidence: Confidence = Confidence.EXACT
) -> WeightMemoryEstimate:
    return WeightMemoryEstimate(
        quantized_payload_bytes=resident_bytes,
        unquantized_payload_bytes=0,
        scale_overhead_bytes=0,
        zero_point_overhead_bytes=0,
        metadata_bytes=0,
        alignment_overhead_bytes=0,
        total_bytes=resident_bytes,
        effective_bits_per_weight=Fraction(16, 1),
        estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
        confidence=confidence,
        assumptions=("weights assumption",),
        warnings=("weights warning",),
        artifact_storage_bytes=8000,
        estimated_resident_weight_bytes=resident_bytes,
    )


def _make_sample_kv(allocated_bytes: int = 2000) -> KVCacheEstimate:
    inputs = KVCacheFormulaInputs(
        num_hidden_layers=32,
        num_attention_heads=32,
        num_key_value_heads=8,
        head_dim=128,
        context_tokens=4096,
        prefix_tokens=0,
        multimodal_tokens=0,
        active_sequences=1,
        kv_dtype=KVDType.FP16,
        bytes_per_element=2,
        block_size=16,
    )
    return KVCacheEstimate(
        formula_inputs=inputs,
        raw_bytes=allocated_bytes - 100,
        allocated_bytes=allocated_bytes,
        alignment_waste_bytes=100,
        bytes_per_token=256,
        bytes_per_sequence=1048576,
    )


def _make_sample_overhead(
    total_range: ByteRange = ByteRange(
        lower_bytes=1000, expected_bytes=1500, upper_bytes=2000
    ),
    confidence: Confidence = Confidence.HIGH,
    is_partial: bool = False,
) -> RuntimeOverheadEstimate:
    ev = Evidence(
        evidence_id="E101",
        source_type="profile",
        source="backend_profile_1",
    )
    return RuntimeOverheadEstimate(
        base_runtime=ByteRange.exact(500),
        parameter_scaled_overhead=ByteRange.exact(200),
        workspace=ByteRange.exact(300),
        graph_capture=ByteRange.exact(0),
        backend_buffers=ByteRange.exact(200),
        allocator_margin=ByteRange.exact(300),
        subtotal_before_allocator_margin=ByteRange.exact(1200),
        total_runtime_overhead=total_range,
        backend_profile_id="vllm_v0",
        backend_version_specifier=">=0.4.0",
        hardware_profile_id="rtx_4090",
        confidence=confidence,
        is_partial=is_partial,
        missing_components=["graph_capture"] if is_partial else [],
        assumptions=["runtime assumption"],
        warnings=["runtime warning"],
        evidence=[ev],
    )


def test_aggregate_complete_estimates():
    weights = _make_sample_weights(4000, Confidence.EXACT)
    kv = _make_sample_kv(2000)
    overhead = _make_sample_overhead(
        ByteRange(lower_bytes=1000, expected_bytes=1500, upper_bytes=2000),
        Confidence.HIGH,
    )

    res = aggregate_memory_requirements(
        weights=weights, kv_cache=kv, runtime_overhead=overhead
    )

    assert not res.is_partial
    assert res.missing_components == []
    assert res.total_requirement is not None
    # total lower = 4000 + 2000 + 1000 = 7000
    assert res.total_requirement.lower_bytes == 7000
    # total expected = 4000 + 2000 + 1500 = 7500
    assert res.total_requirement.expected_bytes == 7500
    # total upper = 4000 + 2000 + 2000 = 8000
    assert res.total_requirement.upper_bytes == 8000
    # minimum confidence between EXACT, EXACT, HIGH -> HIGH
    assert res.confidence == Confidence.HIGH
    assert res.dominant_component_expected == "resident_weights"


def test_aggregate_uses_resident_not_artifact_storage():
    weights = _make_sample_weights(4000)
    kv = _make_sample_kv(2000)
    overhead = _make_sample_overhead(ByteRange.exact(1000))

    res = aggregate_memory_requirements(
        weights=weights, kv_cache=kv, runtime_overhead=overhead
    )

    # 4000 + 2000 + 1000 = 7000, NOT 8000 (artifact storage)
    assert res.total_requirement.expected_bytes == 7000


def test_aggregate_uses_allocated_kv_bytes():
    weights = _make_sample_weights(4000)
    kv = _make_sample_kv(2000)  # raw_bytes = 1900, allocated = 2000
    overhead = _make_sample_overhead(ByteRange.exact(1000))

    res = aggregate_memory_requirements(
        weights=weights, kv_cache=kv, runtime_overhead=overhead
    )

    assert res.kv_cache.memory.expected_bytes == 2000


def test_aggregate_partial_estimate():
    weights = _make_sample_weights(4000)
    kv = _make_sample_kv(2000)
    overhead = _make_sample_overhead(is_partial=True)

    res = aggregate_memory_requirements(
        weights=weights, kv_cache=kv, runtime_overhead=overhead
    )

    assert res.is_partial
    assert res.total_requirement is None
    assert res.known_subtotal.expected_bytes == 7500
    assert res.confidence == Confidence.UNKNOWN
    assert "graph_capture" in res.missing_components

    with pytest.raises(MissingMemoryComponentError):
        aggregate_memory_requirements(
            weights=weights, kv_cache=kv, runtime_overhead=overhead, strict=True
        )


def test_aggregate_tie_breaking_dominant_component():
    weights = _make_sample_weights(3000)
    kv = _make_sample_kv(3000)
    overhead = _make_sample_overhead(ByteRange.exact(3000))

    res = aggregate_memory_requirements(
        weights=weights, kv_cache=kv, runtime_overhead=overhead
    )

    # All three components equal -> tie break order picks resident_weights
    assert res.dominant_component_expected == "resident_weights"
    assert res.dominant_component_upper == "resident_weights"


def test_aggregate_deduplication_and_min_confidence_edge_cases():
    assert _min_confidence() == Confidence.UNKNOWN

    w = WeightMemoryEstimate(
        quantized_payload_bytes=1000,
        unquantized_payload_bytes=0,
        scale_overhead_bytes=0,
        zero_point_overhead_bytes=0,
        metadata_bytes=0,
        alignment_overhead_bytes=0,
        total_bytes=1000,
        effective_bits_per_weight=Fraction(16, 1),
        estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
        confidence=Confidence.UNKNOWN,
        assumptions=("shared_assumption", "weights_only"),
        warnings=("shared_warning", "weights_only_w"),
        estimated_resident_weight_bytes=1000,
    )
    kv = _make_sample_kv(1000)

    ev1 = Evidence(evidence_id="E1", source_type="doc", source="ref1")
    ev2 = Evidence(evidence_id="E1", source_type="doc", source="ref1")

    ov = RuntimeOverheadEstimate(
        base_runtime=ByteRange.exact(1000),
        parameter_scaled_overhead=ByteRange.exact(0),
        workspace=ByteRange.exact(0),
        graph_capture=ByteRange.exact(0),
        backend_buffers=ByteRange.exact(0),
        allocator_margin=ByteRange.exact(0),
        subtotal_before_allocator_margin=ByteRange.exact(1000),
        total_runtime_overhead=ByteRange.exact(1000),
        backend_profile_id="p1",
        backend_version_specifier=None,
        hardware_profile_id="h1",
        confidence=Confidence.UNKNOWN,
        is_partial=False,
        missing_components=[],
        assumptions=["shared_assumption", "runtime_only"],
        warnings=["shared_warning", "runtime_only_w"],
        evidence=[ev1, ev2],
    )

    res = aggregate_memory_requirements(weights=w, kv_cache=kv, runtime_overhead=ov)

    assert not res.is_partial
    assert res.confidence == Confidence.UNKNOWN
    # Deduplication checks
    assert res.assumptions == ["shared_assumption", "weights_only", "runtime_only"]
    assert res.warnings == ["shared_warning", "weights_only_w", "runtime_only_w"]
    assert len(res.evidence) == 1


def test_aggregate_partial_with_empty_missing_components():
    w = _make_sample_weights(1000)
    kv = _make_sample_kv(1000)
    ov = RuntimeOverheadEstimate(
        base_runtime=ByteRange.exact(1000),
        parameter_scaled_overhead=ByteRange.exact(0),
        workspace=ByteRange.exact(0),
        graph_capture=ByteRange.exact(0),
        backend_buffers=ByteRange.exact(0),
        allocator_margin=ByteRange.exact(0),
        subtotal_before_allocator_margin=ByteRange.exact(1000),
        total_runtime_overhead=ByteRange.exact(1000),
        backend_profile_id="p1",
        backend_version_specifier=None,
        hardware_profile_id="h1",
        confidence=Confidence.UNKNOWN,
        is_partial=True,
        missing_components=[],
        assumptions=[],
        warnings=[],
        evidence=[],
    )

    res = aggregate_memory_requirements(weights=w, kv_cache=kv, runtime_overhead=ov)
    assert res.is_partial
    assert res.missing_components == ["runtime_overhead"]
