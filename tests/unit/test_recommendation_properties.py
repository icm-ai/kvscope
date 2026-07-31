"""Hypothesis property-based tests for Phase 8 Recommendation Engine invariants."""

from decimal import Decimal

import hypothesis.strategies as st
from hypothesis import given, settings

from kvscope.api import (
    ByteRange,
    Confidence,
    HardwareMemoryBudget,
    InferenceConfig,
    KVDType,
    MemoryTopology,
    ModelSpec,
    RecommendationContext,
    RecommendationEligibility,
    RecommendationPolicy,
    WeightDType,
    WorkloadConstraints,
    assess_memory_feasibility,
    estimate_kv_cache,
    estimate_runtime_overhead,
    estimate_weight_memory,
    find_safe_active_sequence_limits,
    find_safe_context_limits,
    generate_recommendations,
)
from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.hardware import (
    HardwareProfile,
    HardwareReserveProfile,
    MemoryQuantityInput,
)


def _build_context_and_report(
    context_tokens: int,
    active_seqs: int,
    is_partial: bool = False,
    confidence: Confidence = Confidence.HIGH,
    preserve_graph: bool = False,
):
    model = ModelSpec(
        model_id="prop-model",
        architecture="llama",
        parameter_count=7_000_000_000,
        num_hidden_layers=32,
        num_attention_heads=32,
        num_key_value_heads=32,
        head_dim=128,
        hidden_size=4096,
        vocab_size=32000,
        source="property-test",
    )
    hw_prof = HardwareProfile(
        profile_id="gpu-16gb",
        name="16GB GPU",
        vendor="NVIDIA",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        reserves=HardwareReserveProfile(
            os_reserve=ByteRange.exact(2 * 1024**3),
            display_reserve=ByteRange.exact(0),
            background_process_reserve=ByteRange.exact(0),
            device_specific_reserve=ByteRange.exact(0),
        ),
    )
    bk_prof = BackendProfile(
        profile_id="vllm-test",
        backend_id="vllm",
        display_name="vLLM Test",
        version_specifier=">=0.6.0",
        supported_kv_dtypes=["fp16", "fp8"],
        supported_weight_dtypes=["fp16", "int4"],
        memory_model=BackendMemoryModel(
            base_runtime=ByteRange.exact(1 * 1024**3),
            kv_block_size=16,
            graph_capture_supported=True,
        ),
    )

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=context_tokens,
        max_num_seqs=active_seqs,
        graph_capture_enabled=not preserve_graph,
    )

    weights = estimate_weight_memory(
        parameter_count=model.parameter_count, dtype=WeightDType.FP16
    )

    kv = estimate_kv_cache(model=model, config=cfg, backend=bk_prof.to_spec())
    runtime = estimate_runtime_overhead(
        backend=bk_prof,
        hardware=hw_prof,
        resident_weight_bytes=weights.total_bytes,
        parameter_count=model.parameter_count,
        graph_capture_enabled=True,
    )
    budget = HardwareMemoryBudget(
        physical_total_bytes=hw_prof.total_memory_bytes,
        os_reserve=ByteRange.exact(2 * 1024**3),
        display_reserve=ByteRange.exact(0),
        background_process_reserve=ByteRange.exact(0),
        device_specific_reserve=ByteRange.exact(0),
        user_reserve=ByteRange.exact(0),
        total_non_model_reserve=ByteRange.exact(2 * 1024**3),
        allocatable_before_headroom=ByteRange.exact(14 * 1024**3),
        recommended_headroom=ByteRange.exact(2 * 1024**3),
        recommended_allocatable=ByteRange.exact(12 * 1024**3),
        memory_topology=MemoryTopology.DISCRETE,
        confidence=confidence,
    )

    baseline = assess_memory_feasibility(
        weights=weights, kv_cache=kv, runtime_overhead=runtime, hardware_budget=budget
    )
    if is_partial:
        baseline = baseline.model_copy(
            update={
                "aggregation": baseline.aggregation.model_copy(
                    update={"is_partial": True}
                )
            }
        )

    rec_ctx = RecommendationContext(
        model=model,
        inference_config=cfg,
        current_weight_estimate=weights,
        current_kv_estimate=kv,
        current_runtime_estimate=runtime,
        hardware_budget=budget,
        backend_profile=bk_prof,
        hardware_profile=hw_prof,
        workload_constraints=WorkloadConstraints(
            minimum_context_length=128,
            minimum_active_sequences=1,
            preserve_graph_capture=preserve_graph,
        ),
    )
    return rec_ctx, baseline


@given(
    ctx_len=st.integers(min_value=1024, max_value=65536),
    seqs=st.integers(min_value=1, max_value=32),
)
@settings(max_examples=15)
def test_prop_non_mutation_and_reproducibility(ctx_len: int, seqs: int):
    rec_ctx, baseline = _build_context_and_report(ctx_len, seqs)

    # Snapshot before
    cfg_before = rec_ctx.inference_config.model_dump_json()

    policy = RecommendationPolicy(maximum_candidates=5)
    r1 = generate_recommendations(
        context=rec_ctx, baseline_report=baseline, policy=policy
    )
    r2 = generate_recommendations(
        context=rec_ctx, baseline_report=baseline, policy=policy
    )

    # Invariant: input object not mutated
    assert rec_ctx.inference_config.model_dump_json() == cfg_before

    # Invariant: deterministic report generation
    assert r1.model_dump_json() == r2.model_dump_json()

    # Invariant: max candidate count respected
    num_alts = len(r1.alternatives)
    assert num_alts <= policy.maximum_candidates


@given(
    ctx_len=st.integers(min_value=2048, max_value=32768),
)
@settings(max_examples=10)
def test_prop_context_limit_invariants(ctx_len: int):
    rec_ctx, baseline = _build_context_and_report(ctx_len, active_seqs=2)
    policy = RecommendationPolicy()

    ctx_lim = find_safe_context_limits(context=rec_ctx, policy=policy)

    if ctx_lim.expected_safe_max_context is not None:
        # Invariant: limit is at or above minimum context
        assert (
            ctx_lim.expected_safe_max_context
            >= rec_ctx.workload_constraints.minimum_context_length
        )


@given(
    seqs=st.integers(min_value=1, max_value=16),
)
@settings(max_examples=10)
def test_prop_sequence_limit_invariants(seqs: int):
    rec_ctx, baseline = _build_context_and_report(context_tokens=8192, active_seqs=seqs)
    policy = RecommendationPolicy()

    seq_lim = find_safe_active_sequence_limits(context=rec_ctx, policy=policy)

    if seq_lim.expected_safe_max_sequences is not None:
        # Invariant: sequence limit is at or above minimum active sequences
        assert (
            seq_lim.expected_safe_max_sequences
            >= rec_ctx.workload_constraints.minimum_active_sequences
        )


@given(
    ctx_len=st.integers(min_value=2048, max_value=16384),
)
@settings(max_examples=10)
def test_prop_partial_baseline_ineligible(ctx_len: int):
    rec_ctx, baseline = _build_context_and_report(
        ctx_len, active_seqs=1, is_partial=True
    )

    report = generate_recommendations(context=rec_ctx, baseline_report=baseline)
    assert report.eligibility.eligibility == RecommendationEligibility.INELIGIBLE
    assert report.safe_limits is None
    assert report.primary_recommendation is not None
    assert report.primary_recommendation.action.value == "complete_estimate_required"


@given(
    ctx_len=st.integers(min_value=2048, max_value=16384),
)
@settings(max_examples=10)
def test_prop_preserve_graph_capture_invariant(ctx_len: int):
    rec_ctx, baseline = _build_context_and_report(
        ctx_len, active_seqs=1, preserve_graph=True
    )

    report = generate_recommendations(context=rec_ctx, baseline_report=baseline)

    if report.primary_recommendation is not None:
        assert report.primary_recommendation.action.value != "disable_graph_capture"
    for alt in report.alternatives:
        assert alt.action.value != "disable_graph_capture"
