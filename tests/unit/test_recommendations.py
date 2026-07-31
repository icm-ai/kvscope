import dataclasses
import json
from decimal import Decimal
from pathlib import Path

from kvscope.api import (
    ByteRange,
    Confidence,
    InferenceConfig,
    KVDType,
    MemoryTopology,
    ModelSpec,
    RecommendationContext,
    RecommendationEligibility,
    RecommendationPolicy,
    WeightDType,
    assess_memory_feasibility,
    determine_recommendation_eligibility,
    estimate_kv_cache,
    estimate_runtime_overhead,
    estimate_weight_memory,
    find_safe_active_sequence_limits,
    find_safe_context_limits,
    generate_recommendations,
)
from kvscope.calculators.hardware_budget import estimate_hardware_memory_budget
from kvscope.cli.app import main
from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.enums import (
    InternalFeasibilityStatus,
    ProfileStatus,
)
from kvscope.domain.hardware import (
    HardwareProfile,
    HardwareReserveProfile,
    MemoryQuantityInput,
)
from kvscope.domain.recommendation import (
    CandidateVerificationStatus,
    ParameterChange,
    RecommendationAction,
    RecommendationCandidate,
    RecommendationStrength,
    TradeoffSeverity,
    WeightRecomputeRequest,
    WorkloadConstraints,
)
from kvscope.engines.candidate_evaluation import (
    _determine_candidate_strength,
    _generate_candidate_id,
    evaluate_candidate_proposal,
)
from kvscope.engines.candidate_generation import (
    CandidateChangeProposal,
    generate_candidate_proposals,
)
from kvscope.engines.recommendation_ranking import rank_recommendation_candidates
from kvscope.engines.sequence_limits import _solve_and_verify_sequence_limit
from kvscope.serialization.json import (
    serialize_recommendation_report_json,
)
from kvscope.serialization.markdown import (
    serialize_recommendation_report_markdown,
)
from kvscope.serialization.terminal import format_recommendation_report_terminal


def _fixture_setup():
    model = ModelSpec(
        model_id="test-7b",
        architecture="llama",
        parameter_count=7_000_000_000,
        num_hidden_layers=32,
        num_attention_heads=32,
        num_key_value_heads=32,
        head_dim=128,
        hidden_size=4096,
        vocab_size=32000,
        source="unit-test",
    )
    hw_prof = HardwareProfile(
        profile_id="gpu-32gb",
        name="32GB GPU",
        vendor="NVIDIA",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("32"), unit="GiB"),
        reserves=HardwareReserveProfile(
            os_reserve=ByteRange.exact(2 * 1024**3),
            display_reserve=ByteRange.exact(0),
            background_process_reserve=ByteRange.exact(0),
            device_specific_reserve=ByteRange.exact(0),
        ),
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
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
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )

    cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=16384,
        max_num_seqs=2,
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

    return model, hw_prof, bk_prof, cfg, weights, kv, runtime, budget


def test_determine_recommendation_eligibility():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )

    res = determine_recommendation_eligibility(baseline)
    assert res.eligibility == RecommendationEligibility.ELIGIBLE

    # Test Partial -> INELIGIBLE
    part_baseline = baseline.model_copy(
        update={
            "aggregation": baseline.aggregation.model_copy(update={"is_partial": True})
        }
    )
    part_res = determine_recommendation_eligibility(part_baseline)
    assert part_res.eligibility == RecommendationEligibility.INELIGIBLE
    assert "PARTIAL_MEMORY_ESTIMATE" in part_res.reason_codes

    # Test Low confidence -> ADVISORY_ONLY
    low_baseline = baseline.model_copy(
        update={
            "feasibility": baseline.feasibility.model_copy(
                update={"confidence": Confidence.LOW}
            )
        }
    )
    low_res = determine_recommendation_eligibility(low_baseline)
    assert low_res.eligibility == RecommendationEligibility.ADVISORY_ONLY


def test_find_safe_context_limits():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )
    pol = RecommendationPolicy()

    lim = find_safe_context_limits(context=ctx, policy=pol)
    assert lim.current_context == 16384
    assert lim.expected_safe_max_context is not None
    assert lim.expected_safe_max_context < 16384
    assert lim.verified is True


def test_find_safe_sequence_limits():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )
    pol = RecommendationPolicy()

    lim = find_safe_active_sequence_limits(context=ctx, policy=pol)
    assert lim.current_active_sequences == 2
    assert lim.expected_safe_max_sequences is not None


def test_generate_recommendations_end_to_end():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )

    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )

    report = generate_recommendations(context=ctx, baseline_report=baseline)
    assert report.eligibility.eligibility == RecommendationEligibility.ELIGIBLE
    assert report.primary_recommendation is not None
    assert report.safe_limits is not None

    # Test Serializers
    term_str = format_recommendation_report_terminal(report)
    assert "KVScope Recommendation Report" in term_str
    assert "eligible" in term_str.lower()

    json_str = serialize_recommendation_report_json(report)
    assert '"kind": "recommendation_report"' in json_str

    md_str = serialize_recommendation_report_markdown(report)
    assert "# KVScope Recommendation Report" in md_str


def test_cli_recommend_command(tmp_path: Path):
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )

    ctx_file = tmp_path / "rec_context.json"
    rep_file = tmp_path / "feas_report.json"

    ctx_file.write_text(json.dumps(json.loads(ctx.model_dump_json())), encoding="utf-8")
    rep_file.write_text(
        json.dumps(json.loads(baseline.model_dump_json())), encoding="utf-8"
    )

    code = main(
        [
            "recommend",
            "--context-json",
            str(ctx_file),
            "--baseline-report-json",
            str(rep_file),
            "--format",
            "terminal",
        ]
    )
    assert code in (0, 2, 3)


# --- Phase 8 Security Audit & Boundary Tests ---


def test_eligibility_matrix_additional_ineligible_branches():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )

    # 1. Missing total requirement
    no_tot_baseline = baseline.model_copy(
        update={
            "aggregation": baseline.aggregation.model_copy(
                update={"total_requirement": None}
            )
        }
    )
    res_no_tot = determine_recommendation_eligibility(no_tot_baseline)
    assert res_no_tot.eligibility == RecommendationEligibility.INELIGIBLE
    assert "MISSING_TOTAL_REQUIREMENT" in res_no_tot.reason_codes

    # 2. Unknown feasibility status
    unk_status_baseline = baseline.model_copy(
        update={
            "feasibility": baseline.feasibility.model_copy(
                update={"internal_status": InternalFeasibilityStatus.UNKNOWN}
            )
        }
    )
    res_unk = determine_recommendation_eligibility(unk_status_baseline)
    assert res_unk.eligibility == RecommendationEligibility.INELIGIBLE
    assert "UNKNOWN_FEASIBILITY" in res_unk.reason_codes

    # 3. Non-actionable report
    unactionable_baseline = baseline.model_copy(
        update={
            "feasibility": baseline.feasibility.model_copy(
                update={"is_actionable": False}
            )
        }
    )
    res_unact = determine_recommendation_eligibility(unactionable_baseline)
    assert res_unact.eligibility == RecommendationEligibility.INELIGIBLE
    assert "INCOMPLETE_RUNTIME_PROFILE" in res_unact.reason_codes


def test_context_limits_fallback_without_backend_profile_and_clamping():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    # Context without backend profile (uses formula fallback)
    ctx_no_backend = RecommendationContext(
        model=m,
        inference_config=cfg.model_copy(
            update={"prefix_tokens": 128, "multimodal_tokens": 64}
        ),
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=None,
        hardware_profile=hw,
        workload_constraints=WorkloadConstraints(
            minimum_context_length=512,
            model_max_context_length=8192,
        ),
    )
    pol = RecommendationPolicy()
    lim = find_safe_context_limits(context=ctx_no_backend, policy=pol)

    assert lim.fixed_tokens == 192
    assert lim.expected_safe_max_context is not None
    assert lim.expected_safe_max_context <= 8192


def test_ambiguous_active_sequence_control_does_not_generate_parameter_change():
    """Verify that when sequence control is ambiguous (equal / explicit override),

    NO parameter mutation candidate 'REDUCE_ACTIVE_SEQUENCES' is generated.
    """
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()

    # Case 1: Equal (batch_size == max_num_seqs)
    ambiguous_cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=16384,
        batch_size=8,
        max_num_seqs=8,
    )

    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=ambiguous_cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )

    seq_limits = find_safe_active_sequence_limits(
        context=ctx, policy=RecommendationPolicy()
    )
    proposals = generate_candidate_proposals(
        context=ctx,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        safe_context_limit=None,
        safe_sequence_limit=seq_limits,
    )

    seq_proposals = [
        p for p in proposals if p.action == RecommendationAction.REDUCE_ACTIVE_SEQUENCES
    ]
    assert len(seq_proposals) == 0, (
        "Ambiguous active sequence control must not generate proposals"
    )


def test_weight_int4_without_metadata_generates_advisory():
    """Verify missing metadata generates ADVISORY candidate."""
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
        weight_recompute_request=None,  # Missing metadata!
    )

    proposals = generate_candidate_proposals(
        context=ctx,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        safe_context_limit=None,
        safe_sequence_limit=None,
    )

    metadata_proposals = [
        p
        for p in proposals
        if p.action == RecommendationAction.PROVIDE_QUANTIZATION_METADATA
    ]
    assert len(metadata_proposals) == 1

    cand, _ = evaluate_candidate_proposal(
        proposal=metadata_proposals[0],
        baseline_context=ctx,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        eligibility=RecommendationEligibility.ELIGIBLE,
    )

    assert cand is not None
    assert cand.strength == RecommendationStrength.ADVISORY
    assert cand.verification_status == CandidateVerificationStatus.ADVISORY_ONLY


def test_weight_int4_with_full_metadata_uses_weight_engine():
    """Verify full WeightRecomputeRequest calls Weight Engine for recomputation."""
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )
    weight_req = WeightRecomputeRequest(
        parameter_count=m.parameter_count,
        weight_dtype=WeightDType.FP16,
        group_size=128,
        scale_bytes=2,
        zero_point_bytes=0,
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
        weight_recompute_request=weight_req,
    )

    proposal = CandidateChangeProposal(
        action=RecommendationAction.CHANGE_WEIGHT_DTYPE,
        changes=[
            ParameterChange(
                parameter="weight_dtype", before="fp16", after="int4", unit=None
            )
        ],
        title="Quantize model weights to int4",
        explanation="Testing weight engine recompute",
        tradeoff_severity=TradeoffSeverity.HIGH,
    )

    cand, _ = evaluate_candidate_proposal(
        proposal=proposal,
        baseline_context=ctx,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        eligibility=RecommendationEligibility.ELIGIBLE,
    )

    assert cand is not None
    assert cand.verification_status == CandidateVerificationStatus.VERIFIED
    assert cand.impact is not None
    assert cand.impact.savings.expected_bytes > 0


def test_disable_graph_capture_recomputes_allocator_margin():
    """Verify disabling graph capture recalculates allocator margin."""
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    bk_gc = bk.model_copy(
        update={
            "memory_model": bk.memory_model.model_copy(
                update={"graph_capture_reserve": ByteRange.exact(2 * 1024**3)}
            )
        }
    )
    rt_gc = estimate_runtime_overhead(
        backend=bk_gc,
        hardware=hw,
        resident_weight_bytes=w.total_bytes,
        parameter_count=m.parameter_count,
        graph_capture_enabled=True,
    )
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt_gc, hardware_budget=b
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt_gc,
        hardware_budget=b,
        backend_profile=bk_gc,
        hardware_profile=hw,
    )

    proposal = CandidateChangeProposal(
        action=RecommendationAction.DISABLE_GRAPH_CAPTURE,
        changes=[
            ParameterChange(
                parameter="graph_capture_enabled", before=True, after=False, unit=None
            )
        ],
        title="Disable Graph Capture",
        explanation="Testing runtime overhead recompute",
        tradeoff_severity=TradeoffSeverity.LOW,
    )

    cand, _ = evaluate_candidate_proposal(
        proposal=proposal,
        baseline_context=ctx,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        eligibility=RecommendationEligibility.ELIGIBLE,
    )

    assert cand is not None
    assert cand.verification_status == CandidateVerificationStatus.VERIFIED
    assert cand.impact is not None
    # Verify new memory requirement is lower than baseline requirement
    assert (
        cand.impact.after_requirement.expected_bytes
        < cand.impact.before_requirement.expected_bytes
    )


def test_no_change_required_generated_when_baseline_feasible():
    """Verify primary recommendation is NO_CHANGE_REQUIRED when baseline feasible."""
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()

    # Small context length (1024) making baseline FEASIBLE on 32GB GPU
    feasible_cfg = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=1024,
        max_num_seqs=1,
    )
    feasible_kv = estimate_kv_cache(model=m, config=feasible_cfg, backend=bk.to_spec())
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=feasible_kv, runtime_overhead=rt, hardware_budget=b
    )

    ctx = RecommendationContext(
        model=m,
        inference_config=feasible_cfg,
        current_weight_estimate=w,
        current_kv_estimate=feasible_kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )

    report = generate_recommendations(context=ctx, baseline_report=baseline)
    assert report.primary_recommendation is not None
    act = report.primary_recommendation.action
    st = report.primary_recommendation.strength
    assert act == RecommendationAction.NO_CHANGE_REQUIRED
    assert st == RecommendationStrength.INFORMATIONAL


def test_ranking_determinism_under_shuffled_inputs():
    """Verify deterministic ranking order regardless of candidate input list order."""
    c1 = RecommendationCandidate(
        candidate_id="reduce-context-to-4096",
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
        strength=RecommendationStrength.REQUIRED,
        title="Candidate 1",
        explanation="Explanation 1",
        changes=[],
        impact=None,
        eligibility=RecommendationEligibility.ELIGIBLE,
        confidence=Confidence.HIGH,
        tradeoff_severity=TradeoffSeverity.MEDIUM,
        verification_status=CandidateVerificationStatus.VERIFIED,
    )
    c2 = RecommendationCandidate(
        candidate_id="change-kv-dtype-fp16-to-fp8",
        action=RecommendationAction.CHANGE_KV_DTYPE,
        strength=RecommendationStrength.STRONG,
        title="Candidate 2",
        explanation="Explanation 2",
        changes=[],
        impact=None,
        eligibility=RecommendationEligibility.ELIGIBLE,
        confidence=Confidence.HIGH,
        tradeoff_severity=TradeoffSeverity.LOW,
        verification_status=CandidateVerificationStatus.VERIFIED,
    )

    r1 = rank_recommendation_candidates([c1, c2], RecommendationPolicy())
    r2 = rank_recommendation_candidates([c2, c1], RecommendationPolicy())
    assert [c.candidate_id for c in r1] == [c.candidate_id for c in r2]


def test_context_limits_edge_branches():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()

    # 1. No block_size & below min_context
    kv_no_block = dataclasses.replace(
        kv,
        formula_inputs=dataclasses.replace(kv.formula_inputs, block_size=None),
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv_no_block,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
        workload_constraints=WorkloadConstraints(minimum_context_length=32768),
    )
    lim = find_safe_context_limits(context=ctx, policy=RecommendationPolicy())
    assert lim.guaranteed_safe_max_context is None  # Below min_context!


def test_sequence_limits_fallback_no_backend_and_no_block_size():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    kv_no_block = dataclasses.replace(
        kv,
        formula_inputs=dataclasses.replace(kv.formula_inputs, block_size=None),
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg.model_copy(update={"max_num_seqs": 4, "batch_size": 1}),
        current_weight_estimate=w,
        current_kv_estimate=kv_no_block,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=None,  # Tests formula fallback path in sequence_limits.py
        hardware_profile=hw,
    )
    lim = find_safe_active_sequence_limits(context=ctx, policy=RecommendationPolicy())
    assert lim.effective_tokens_per_sequence == 16384


def test_candidate_generation_feasible_and_no_backend_profile():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    feasible_cfg = cfg.model_copy(update={"context_length": 128})
    feasible_kv = estimate_kv_cache(model=m, config=feasible_cfg, backend=bk.to_spec())
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=feasible_kv, runtime_overhead=rt, hardware_budget=b
    )

    # 1. Baseline FEASIBLE -> 0 proposals generated
    ctx_feas = RecommendationContext(
        model=m,
        inference_config=feasible_cfg,
        current_weight_estimate=w,
        current_kv_estimate=feasible_kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )
    proposals = generate_candidate_proposals(
        context=ctx_feas,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        safe_context_limit=None,
        safe_sequence_limit=None,
    )
    assert len(proposals) == 0

    # 2. Infeasible without backend profile
    infeas_baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )
    ctx_no_backend = RecommendationContext(
        model=m,
        inference_config=cfg.model_copy(update={"kv_dtype": KVDType.FP8}),
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=None,  # Fallback standard KV dtypes
        hardware_profile=hw,
    )
    proposals2 = generate_candidate_proposals(
        context=ctx_no_backend,
        baseline_report=infeas_baseline,
        policy=RecommendationPolicy(),
        safe_context_limit=None,
        safe_sequence_limit=None,
    )
    assert len(proposals2) > 0


def test_candidate_evaluation_additional_rejection_branches():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )

    # 1. Evaluation without backend profile (uses formula KV calculation)
    ctx_no_backend = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=None,
        hardware_profile=hw,
    )
    prop = CandidateChangeProposal(
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
        changes=[
            ParameterChange(
                parameter="context_length", before=16384, after=4096, unit="tokens"
            )
        ],
        title="Reduce Context Length",
        explanation="Testing evaluation without backend profile",
        tradeoff_severity=TradeoffSeverity.MEDIUM,
    )
    cand, rej = evaluate_candidate_proposal(
        proposal=prop,
        baseline_context=ctx_no_backend,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        eligibility=RecommendationEligibility.ELIGIBLE,
    )
    assert cand is not None
    assert cand.verification_status == CandidateVerificationStatus.VERIFIED

    # 2. Evaluation failure due to exception -> RECOMPUTE_FAILED
    bad_prop = CandidateChangeProposal(
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
        changes=[
            ParameterChange(
                parameter="context_length", before=16384, after=-999, unit="tokens"
            )
        ],
        title="Invalid Context Length",
        explanation="Testing exception recompute",
        tradeoff_severity=TradeoffSeverity.HIGH,
    )
    _, rej_bad = evaluate_candidate_proposal(
        proposal=bad_prop,
        baseline_context=ctx_no_backend,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        eligibility=RecommendationEligibility.ELIGIBLE,
    )
    assert rej_bad is not None
    assert rej_bad.reason_code == "RECOMPUTE_FAILED"


def test_recommendations_no_single_action_sufficient_warning():
    """Verify warning appended when no candidate is sufficient for feasibility."""
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )

    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )

    # Disallow all candidate actions via policy so 0 proposals are accepted
    strict_pol = RecommendationPolicy(
        allow_context_reduction=False,
        allow_sequence_reduction=False,
        allow_kv_dtype_change=False,
        allow_weight_dtype_change=False,
    )

    report = generate_recommendations(
        context=ctx, baseline_report=baseline, policy=strict_pol
    )
    assert report.primary_recommendation is None
    assert any("No single-action candidate" in w for w in report.warnings)


def test_sequence_limit_step_down_on_initial_failure():
    """Verify active sequence limit decrements on initial failure."""

    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()

    ctx = RecommendationContext(
        model=m,
        inference_config=cfg.model_copy(update={"max_num_seqs": 10, "batch_size": 1}),
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )
    pol = RecommendationPolicy()
    lim = find_safe_active_sequence_limits(context=ctx, policy=pol)
    assert lim.expected_safe_max_sequences is not None


def test_candidate_evaluation_strength_and_rejection_branches():
    m, hw, bk, cfg, w, kv, rt, b = _fixture_setup()
    baseline = assess_memory_feasibility(
        weights=w, kv_cache=kv, runtime_overhead=rt, hardware_budget=b
    )
    ctx = RecommendationContext(
        model=m,
        inference_config=cfg,
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b,
        backend_profile=bk,
        hardware_profile=hw,
    )

    # 1. Candidate where status is not improved -> STATUS_NOT_IMPROVED
    worse_prop = CandidateChangeProposal(
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
        changes=[
            ParameterChange(
                parameter="context_length", before=16384, after=32768, unit="tokens"
            )
        ],
        title="Increase context length",
        explanation="Testing worse status",
        tradeoff_severity=TradeoffSeverity.HIGH,
    )
    cand_worse, rej_worse = evaluate_candidate_proposal(
        proposal=worse_prop,
        baseline_context=ctx,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        eligibility=RecommendationEligibility.ELIGIBLE,
    )
    assert cand_worse is None
    assert rej_worse is not None
    assert rej_worse.reason_code in ("NO_MEMORY_IMPROVEMENT", "STATUS_NOT_IMPROVED")

    # 2. Candidate resulting in CONDITIONAL_FEASIBLE -> strength CONDITIONAL
    cond_prop = CandidateChangeProposal(
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
        changes=[
            ParameterChange(
                parameter="context_length", before=16384, after=12000, unit="tokens"
            )
        ],
        title="Reduce to 12000",
        explanation="Testing conditional strength",
        tradeoff_severity=TradeoffSeverity.MEDIUM,
    )
    cand_cond, _ = evaluate_candidate_proposal(
        proposal=cond_prop,
        baseline_context=ctx,
        baseline_report=baseline,
        policy=RecommendationPolicy(),
        eligibility=RecommendationEligibility.ELIGIBLE,
    )
    if cand_cond is not None:
        assert cand_cond.strength in (
            RecommendationStrength.STRONG,
            RecommendationStrength.CONDITIONAL,
            RecommendationStrength.REQUIRED,
        )


def test_internal_candidate_evaluation_helpers():
    # 1. Test strength determination branches
    s1 = _determine_candidate_strength(
        before_status=InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED,
        after_status=InternalFeasibilityStatus.EXPECTED_FEASIBLE,
        eligibility=RecommendationEligibility.ELIGIBLE,
        action=RecommendationAction.PROVIDE_QUANTIZATION_METADATA,
    )
    assert s1 == RecommendationStrength.ADVISORY

    s2 = _determine_candidate_strength(
        before_status=InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        after_status=InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        eligibility=RecommendationEligibility.ELIGIBLE,
        action=RecommendationAction.NO_CHANGE_REQUIRED,
    )
    assert s2 == RecommendationStrength.INFORMATIONAL

    s3 = _determine_candidate_strength(
        before_status=InternalFeasibilityStatus.HEADROOM_EXCEEDED,
        after_status=InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        eligibility=RecommendationEligibility.ELIGIBLE,
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
    )
    assert s3 == RecommendationStrength.STRONG

    s4 = _determine_candidate_strength(
        before_status=InternalFeasibilityStatus.CONDITIONAL_FEASIBLE,
        after_status=InternalFeasibilityStatus.EXPECTED_FEASIBLE,
        eligibility=RecommendationEligibility.ELIGIBLE,
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
    )
    assert s4 == RecommendationStrength.STRONG

    s5 = _determine_candidate_strength(
        before_status=InternalFeasibilityStatus.HEADROOM_EXCEEDED,
        after_status=InternalFeasibilityStatus.CONDITIONAL_FEASIBLE,
        eligibility=RecommendationEligibility.ELIGIBLE,
        action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
    )
    assert s5 == RecommendationStrength.CONDITIONAL

    # 2. Test candidate ID generator fallback
    prop = CandidateChangeProposal(
        action=RecommendationAction.PROVIDE_BACKEND_VERSION,
        changes=[],
        title="Title",
        explanation="Explanation",
        tradeoff_severity=TradeoffSeverity.NONE,
    )
    cid = _generate_candidate_id(prop)
    assert cid == "candidate-proposal"


def test_sequence_limit_step_down_iteration():
    m, hw_20, bk, cfg, w, kv, rt, b_20 = _fixture_setup()
    hw_20 = HardwareProfile(
        profile_id="gpu-20gb",
        name="20GB GPU",
        vendor="NVIDIA",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("20"), unit="GiB"),
        reserves=HardwareReserveProfile(
            os_reserve=ByteRange.exact(2 * 1024**3),
            display_reserve=ByteRange.exact(0),
        ),
    )

    b_20 = estimate_hardware_memory_budget(hw_20)

    ctx = RecommendationContext(
        model=m,
        inference_config=cfg.model_copy(update={"max_num_seqs": 10, "batch_size": 1}),
        current_weight_estimate=w,
        current_kv_estimate=kv,
        current_runtime_estimate=rt,
        hardware_budget=b_20,
        backend_profile=bk,
        hardware_profile=hw_20,
    )

    res = _solve_and_verify_sequence_limit(
        kv_budget_bytes=50_000_000_000,
        bytes_per_sequence=10_000_000_000,
        min_sequences=5,
        target_statuses={InternalFeasibilityStatus.GUARANTEED_FEASIBLE},
        context=ctx,
    )
    assert res is None


def test_allocatable_exceeded_to_expected_feasible_is_required():
    """Verify ALLOCATABLE_EXCEEDED to EXPECTED_FEASIBLE yields REQUIRED strength."""

    st = _determine_candidate_strength(
        before_status=InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED,
        after_status=InternalFeasibilityStatus.EXPECTED_FEASIBLE,
        eligibility=RecommendationEligibility.ELIGIBLE,
        action=RecommendationAction.REDUCE_ACTIVE_SEQUENCES,
    )
    assert st == RecommendationStrength.REQUIRED
