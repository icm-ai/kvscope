from decimal import Decimal

from kvscope.calculators.hardware_budget import estimate_hardware_memory_budget
from kvscope.calculators.kv_cache import estimate_kv_cache
from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.calculators.weights import (
    estimate_weight_memory,
)
from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.config import InferenceConfig
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    MemoryTopology,
    ProfileStatus,
)
from kvscope.domain.hardware import (
    HardwareProfile,
    HardwareReserveProfile,
    MemoryQuantityInput,
)
from kvscope.domain.model import ModelSpec
from kvscope.domain.ranges import ByteRange
from kvscope.domain.recommendation import (
    CandidateVerificationStatus,
    RecommendationAction,
    RecommendationContext,
    RecommendationEligibility,
    RecommendationPolicy,
    RecommendationStrength,
    WeightRecomputeRequest,
)
from kvscope.engines.analysis import assess_memory_feasibility
from kvscope.engines.recommendations import generate_recommendations


def _make_hardware_profile(total_gb: int = 16) -> HardwareProfile:
    res_bytes = 2 * 1024 * 1024 * 1024
    return HardwareProfile(
        profile_id=f"gpu-{total_gb}gb",
        name=f"{total_gb}GB GPU",
        vendor="NVIDIA",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal(str(total_gb)), unit="GiB"),
        reserves=HardwareReserveProfile(
            os_reserve=ByteRange.exact(res_bytes),
            display_reserve=ByteRange.exact(0),
            background_process_reserve=ByteRange.exact(0),
            device_specific_reserve=ByteRange.exact(0),
        ),
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )


def _make_backend_profile() -> BackendProfile:
    return BackendProfile(
        profile_id="vllm-test",
        backend_id="vllm",
        display_name="vLLM Test",
        version_specifier=">=0.6.0",
        supported_kv_dtypes=["fp16", "bf16", "fp8", "int8"],
        supported_weight_dtypes=["fp16", "int4", "int8"],
        memory_model=BackendMemoryModel(
            base_runtime=ByteRange.exact(1 * 1024**3),
            graph_capture_reserve=ByteRange.exact(2 * 1024**3),
            kv_block_size=16,
            graph_capture_supported=True,
        ),
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )


def _make_model_spec(param_b: float = 7.0) -> ModelSpec:
    return ModelSpec(
        model_id="test-model",
        architecture="llama",
        parameter_count=int(param_b * 1e9),
        num_hidden_layers=32,
        num_attention_heads=32,
        num_key_value_heads=32,
        head_dim=128,
        hidden_size=4096,
        vocab_size=32000,
        source="golden-test",
    )


# Case A: Context Reduction Solves Headroom
def test_golden_case_a_context_reduction():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(24)  # 24GB Total
    bk_prof = _make_backend_profile()

    # High context causing HEADROOM_EXCEEDED
    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=32768,
        max_num_seqs=1,
        graph_capture_enabled=True,
    )

    weights = estimate_weight_memory(
        parameter_count=model.parameter_count,
        dtype=WeightDType.FP16,
    )
    kv = estimate_kv_cache(model=model, config=cfg, backend=bk_prof.to_spec())
    runtime = estimate_runtime_overhead(
        backend=bk_prof,
        hardware=hw_prof,
        resident_weight_bytes=weights.total_bytes,
        parameter_count=model.parameter_count,
        graph_capture_enabled=cfg.graph_capture_enabled,
    )
    budget = estimate_hardware_memory_budget(hw_prof)

    baseline_report = assess_memory_feasibility(
        weights=weights,
        kv_cache=kv,
        runtime_overhead=runtime,
        hardware_budget=budget,
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
    )

    report = generate_recommendations(context=rec_ctx, baseline_report=baseline_report)

    assert report.eligibility.eligibility == RecommendationEligibility.ELIGIBLE
    assert report.primary_recommendation is not None
    assert (
        report.primary_recommendation.action
        == RecommendationAction.REDUCE_CONTEXT_LENGTH
    )
    assert report.primary_recommendation.changes[0].parameter == "context_length"
    assert int(report.primary_recommendation.changes[0].after) < 32768
    assert report.primary_recommendation.impact.after_status in (
        InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        InternalFeasibilityStatus.EXPECTED_FEASIBLE,
    )


# Case B: Active Sequences Reduction
def test_golden_case_b_sequence_reduction():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(32)
    bk_prof = _make_backend_profile()

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=8192,
        max_num_seqs=16,
        graph_capture_enabled=True,
    )

    weights = estimate_weight_memory(
        parameter_count=model.parameter_count,
        dtype=WeightDType.FP16,
    )
    kv = estimate_kv_cache(model=model, config=cfg, backend=bk_prof.to_spec())
    runtime = estimate_runtime_overhead(
        backend=bk_prof,
        hardware=hw_prof,
        resident_weight_bytes=weights.total_bytes,
        parameter_count=model.parameter_count,
        graph_capture_enabled=True,
    )
    budget = estimate_hardware_memory_budget(hw_prof)

    baseline_report = assess_memory_feasibility(
        weights=weights,
        kv_cache=kv,
        runtime_overhead=runtime,
        hardware_budget=budget,
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
    )

    policy = RecommendationPolicy(
        allow_context_reduction=False,
        allow_sequence_reduction=True,
        allow_kv_dtype_change=False,
        allow_weight_dtype_change=False,
        allow_disable_graph_capture=False,
    )
    report = generate_recommendations(
        context=rec_ctx, baseline_report=baseline_report, policy=policy
    )

    assert report.eligibility.eligibility == RecommendationEligibility.ELIGIBLE
    assert report.primary_recommendation is not None
    assert (
        report.primary_recommendation.action
        == RecommendationAction.REDUCE_ACTIVE_SEQUENCES
    )
    assert report.primary_recommendation.strength == RecommendationStrength.REQUIRED
    assert report.primary_recommendation.impact.before_status in (
        InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED,
        InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED,
    )

    assert report.primary_recommendation.impact.after_status in (
        InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        InternalFeasibilityStatus.EXPECTED_FEASIBLE,
    )
    assert (
        report.primary_recommendation.verification_status
        == CandidateVerificationStatus.VERIFIED
    )
    assert report.safe_limits is not None
    assert report.safe_limits.active_sequences is not None
    assert report.safe_limits.active_sequences.expected_safe_max_sequences is not None
    assert report.safe_limits.active_sequences.expected_safe_max_sequences < 16


# Case C: KV Dtype Candidate
def test_golden_case_c_kv_dtype_candidate():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(16)
    bk_prof = _make_backend_profile()

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=8192,
        max_num_seqs=4,
        graph_capture_enabled=True,
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
    budget = estimate_hardware_memory_budget(hw_prof)

    baseline_report = assess_memory_feasibility(
        weights=weights,
        kv_cache=kv,
        runtime_overhead=runtime,
        hardware_budget=budget,
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
    )

    policy = RecommendationPolicy(
        allow_context_reduction=False, allow_sequence_reduction=False
    )
    report = generate_recommendations(
        context=rec_ctx, baseline_report=baseline_report, policy=policy
    )

    assert report.primary_recommendation is not None
    assert report.primary_recommendation.action == RecommendationAction.CHANGE_KV_DTYPE
    assert report.primary_recommendation.changes[0].after in ("fp8", "int8")


# Case D: Weight INT4 Candidate
def test_golden_case_d_weight_int4_candidate():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(16)
    bk_prof = _make_backend_profile()

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=4096,
        max_num_seqs=1,
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
    )
    budget = estimate_hardware_memory_budget(hw_prof)

    baseline_report = assess_memory_feasibility(
        weights=weights, kv_cache=kv, runtime_overhead=runtime, hardware_budget=budget
    )

    weight_req = WeightRecomputeRequest(
        parameter_count=model.parameter_count,
        weight_dtype=WeightDType.FP16,
        group_size=128,
        scale_bytes=2,
        zero_point_bytes=0,
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
        weight_recompute_request=weight_req,
    )

    policy = RecommendationPolicy(
        allow_context_reduction=False,
        allow_sequence_reduction=False,
        allow_kv_dtype_change=False,
        allow_weight_dtype_change=True,
    )

    report = generate_recommendations(
        context=rec_ctx, baseline_report=baseline_report, policy=policy
    )

    assert report.primary_recommendation is not None
    assert (
        report.primary_recommendation.action == RecommendationAction.CHANGE_WEIGHT_DTYPE
    )
    assert report.primary_recommendation.changes[0].after == "int4"


# Case E: Disable Graph Capture
def test_golden_case_e_disable_graph_capture():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(20)
    bk_prof = _make_backend_profile()

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=4096,
        max_num_seqs=1,
        graph_capture_enabled=True,
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

    budget = estimate_hardware_memory_budget(hw_prof)

    baseline_report = assess_memory_feasibility(
        weights=weights, kv_cache=kv, runtime_overhead=runtime, hardware_budget=budget
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
    )

    policy = RecommendationPolicy(
        allow_context_reduction=False,
        allow_sequence_reduction=False,
        allow_kv_dtype_change=False,
        allow_weight_dtype_change=False,
        allow_disable_graph_capture=True,
    )

    report = generate_recommendations(
        context=rec_ctx, baseline_report=baseline_report, policy=policy
    )

    assert report.primary_recommendation is not None
    assert (
        report.primary_recommendation.action
        == RecommendationAction.DISABLE_GRAPH_CAPTURE
    )


# Case F: Partial Ineligible
def test_golden_case_f_partial_ineligible():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(16)
    bk_prof = _make_backend_profile()

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=4096,
        max_num_seqs=1,
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
    )

    budget = estimate_hardware_memory_budget(hw_prof)

    partial_baseline = assess_memory_feasibility(
        weights=weights, kv_cache=kv, runtime_overhead=runtime, hardware_budget=budget
    )
    # Simulate partial aggregation
    partial_baseline = partial_baseline.model_copy(
        update={
            "aggregation": partial_baseline.aggregation.model_copy(
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
    )

    report = generate_recommendations(context=rec_ctx, baseline_report=partial_baseline)

    assert report.eligibility.eligibility == RecommendationEligibility.INELIGIBLE
    assert report.primary_recommendation is not None
    assert (
        report.primary_recommendation.action
        == RecommendationAction.COMPLETE_ESTIMATE_REQUIRED
    )
    assert report.safe_limits is None


# Case G: Low Confidence Advisory
def test_golden_case_g_low_confidence_advisory():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(16)
    bk_prof = _make_backend_profile()

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=32768,
        max_num_seqs=1,
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
    )

    budget = estimate_hardware_memory_budget(hw_prof).model_copy(
        update={"confidence": Confidence.LOW}
    )

    low_conf_baseline = assess_memory_feasibility(
        weights=weights, kv_cache=kv, runtime_overhead=runtime, hardware_budget=budget
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
    )

    report = generate_recommendations(
        context=rec_ctx, baseline_report=low_conf_baseline
    )

    assert report.eligibility.eligibility == RecommendationEligibility.ADVISORY_ONLY
    assert report.primary_recommendation is not None
    assert report.primary_recommendation.strength == RecommendationStrength.ADVISORY


# Case H: No Change Required
def test_golden_case_h_no_change_required():
    model = _make_model_spec(7.0)
    hw_prof = _make_hardware_profile(32)  # 32GB GPU -> plenty of memory
    bk_prof = _make_backend_profile()

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=2048,
        max_num_seqs=1,
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
    )

    budget = estimate_hardware_memory_budget(hw_prof)

    baseline_report = assess_memory_feasibility(
        weights=weights, kv_cache=kv, runtime_overhead=runtime, hardware_budget=budget
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
    )

    report = generate_recommendations(context=rec_ctx, baseline_report=baseline_report)

    assert report.eligibility.eligibility == RecommendationEligibility.ELIGIBLE
    assert report.primary_recommendation is not None
    assert (
        report.primary_recommendation.action == RecommendationAction.NO_CHANGE_REQUIRED
    )
    assert (
        report.primary_recommendation.strength == RecommendationStrength.INFORMATIONAL
    )
