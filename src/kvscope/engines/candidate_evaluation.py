"""Engine for evaluating recommendation candidate proposals."""

from kvscope.calculators.kv_cache import calculate_kv_cache, estimate_kv_cache
from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.calculators.weights import (
    estimate_weight_memory,
)
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import InternalFeasibilityStatus
from kvscope.domain.recommendation import (
    CandidateMemoryImpact,
    CandidateVerificationStatus,
    RecommendationAction,
    RecommendationCandidate,
    RecommendationContext,
    RecommendationEligibility,
    RecommendationPolicy,
    RecommendationStrength,
    RejectedRecommendationCandidate,
)
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.domain.signed_ranges import (
    calculate_memory_savings,
    subtract_byte_ranges,
)
from kvscope.engines.analysis import assess_memory_feasibility
from kvscope.engines.candidate_generation import CandidateChangeProposal

# Risk status rank ordering (lower is better/safer)
INTERNAL_STATUS_RISK_RANK: dict[InternalFeasibilityStatus, int] = {
    InternalFeasibilityStatus.GUARANTEED_FEASIBLE: 0,
    InternalFeasibilityStatus.EXPECTED_FEASIBLE: 1,
    InternalFeasibilityStatus.CONDITIONAL_FEASIBLE: 2,
    InternalFeasibilityStatus.HEADROOM_EXCEEDED: 3,
    InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED: 4,
    InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED: 5,
    InternalFeasibilityStatus.UNKNOWN: 99,
}


def _determine_candidate_strength(
    *,
    before_status: InternalFeasibilityStatus,
    after_status: InternalFeasibilityStatus,
    eligibility: RecommendationEligibility,
    action: RecommendationAction,
) -> RecommendationStrength:
    """Determine recommendation strength based on before and after status."""
    if action in (
        RecommendationAction.COMPLETE_ESTIMATE_REQUIRED,
        RecommendationAction.PROVIDE_BACKEND_VERSION,
        RecommendationAction.PROVIDE_QUANTIZATION_METADATA,
        RecommendationAction.CALIBRATE_RUNTIME_OVERHEAD,
    ):
        return RecommendationStrength.ADVISORY

    if action == RecommendationAction.NO_CHANGE_REQUIRED:
        return RecommendationStrength.INFORMATIONAL

    if eligibility == RecommendationEligibility.ADVISORY_ONLY:
        return RecommendationStrength.ADVISORY

    before_rank = INTERNAL_STATUS_RISK_RANK.get(before_status, 99)
    after_rank = INTERNAL_STATUS_RISK_RANK.get(after_status, 99)

    if (
        before_status
        in (
            InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED,
            InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED,
        )
        and after_rank <= 3
    ):
        return RecommendationStrength.REQUIRED

    if before_status == InternalFeasibilityStatus.HEADROOM_EXCEEDED and after_rank <= 1:
        return RecommendationStrength.STRONG

    if (
        before_status == InternalFeasibilityStatus.CONDITIONAL_FEASIBLE
        and after_rank <= 1
    ):
        return RecommendationStrength.STRONG

    if after_status == InternalFeasibilityStatus.CONDITIONAL_FEASIBLE:
        return RecommendationStrength.CONDITIONAL

    if after_rank < before_rank:
        return RecommendationStrength.STRONG

    return RecommendationStrength.CONDITIONAL


def evaluate_candidate_proposal(
    *,
    proposal: CandidateChangeProposal,
    baseline_context: RecommendationContext,
    baseline_report: MemoryFeasibilityReport,
    policy: RecommendationPolicy,
    eligibility: RecommendationEligibility,
) -> tuple[RecommendationCandidate | None, RejectedRecommendationCandidate | None]:
    """Evaluate a candidate proposal by re-computing only affected components."""
    action = proposal.action
    cfg = baseline_context.inference_config

    # Handle advisory data requirements that do not alter parameters
    if proposal.is_advisory_data_requirement:
        cand_id = (
            proposal.data_requirement_code.lower().replace("_", "-")
            if proposal.data_requirement_code
            else "data-requirement"
        )
        return (
            RecommendationCandidate(
                candidate_id=cand_id,
                action=action,
                strength=RecommendationStrength.ADVISORY,
                title=proposal.title,
                explanation=proposal.explanation,
                changes=[],
                impact=None,
                eligibility=eligibility,
                confidence=baseline_report.feasibility.confidence,
                source_constraint_codes=proposal.source_constraint_codes,
                tradeoff_severity=proposal.tradeoff_severity,
                tradeoffs=proposal.tradeoffs,
                verification_status=CandidateVerificationStatus.ADVISORY_ONLY,
            ),
            None,
        )

    # 1. Apply single parameter change to copy of InferenceConfig
    trial_weight_est = baseline_context.current_weight_estimate
    trial_kv_est = baseline_context.current_kv_estimate
    trial_runtime_est = baseline_context.current_runtime_estimate

    try:
        if action in (
            RecommendationAction.REDUCE_CONTEXT_LENGTH,
            RecommendationAction.REDUCE_ACTIVE_SEQUENCES,
            RecommendationAction.CHANGE_KV_DTYPE,
        ):
            update_dict: dict[str, object] = {}
            for chg in proposal.changes:
                if chg.parameter == "context_length":
                    update_dict["context_length"] = chg.after
                elif chg.parameter in (
                    "active_sequences",
                    "max_num_seqs",
                    "batch_size",
                ):
                    valid_sources = ("max_num_seqs", "batch_size")
                    param_key = (
                        chg.parameter
                        if chg.parameter in valid_sources
                        else (
                            cfg.active_sequences_source
                            if cfg.active_sequences_source in valid_sources
                            else "active_sequences_override"
                        )
                    )
                    update_dict[param_key] = chg.after

                elif chg.parameter == "kv_dtype":
                    update_dict["kv_dtype"] = KVDType(str(chg.after))

            trial_cfg = cfg.model_copy(update=update_dict)

            if baseline_context.backend_profile is not None:
                trial_kv_est = estimate_kv_cache(
                    model=baseline_context.model,
                    config=trial_cfg,
                    backend=baseline_context.backend_profile.to_spec(),
                )
            else:
                inputs = baseline_context.current_kv_estimate.formula_inputs
                updated_inputs = type(inputs)(
                    num_hidden_layers=inputs.num_hidden_layers,
                    num_attention_heads=inputs.num_attention_heads,
                    num_key_value_heads=inputs.num_key_value_heads,
                    head_dim=inputs.head_dim,
                    context_tokens=trial_cfg.context_length,
                    prefix_tokens=inputs.prefix_tokens,
                    multimodal_tokens=inputs.multimodal_tokens,
                    active_sequences=trial_cfg.active_sequences,
                    kv_dtype=trial_cfg.kv_dtype,
                    bytes_per_element=trial_cfg.kv_dtype.bytes_per_element,
                    block_size=inputs.block_size,
                    active_sequences_source=inputs.active_sequences_source,
                    prefix_shared=inputs.prefix_shared,
                )
                trial_kv_est = calculate_kv_cache(updated_inputs)

        elif action == RecommendationAction.CHANGE_WEIGHT_DTYPE:
            target_dtype_str = str(proposal.changes[0].after)
            target_weight_dtype = WeightDType(target_dtype_str)
            req = baseline_context.weight_recompute_request

            if req is not None and req.parameter_count > 0:
                trial_weight_est = estimate_weight_memory(
                    parameter_count=req.parameter_count,
                    dtype=target_weight_dtype,
                    quantized_parameter_count=req.quantized_parameter_count,
                    unquantized_parameter_count=req.unquantized_parameter_count,
                    unquantized_dtype=req.unquantized_dtype,
                    quantization_bits=req.quant_bits,
                    group_size=req.group_size or 128,
                    scale_bytes_per_group=req.scale_bytes,
                    zero_point_bytes_per_group=req.zero_point_bytes,
                    metadata_bytes=req.metadata_bytes,
                    alignment_bytes=req.alignment_bytes,
                )

        elif action == RecommendationAction.DISABLE_GRAPH_CAPTURE:
            if (
                baseline_context.backend_profile is not None
                and baseline_context.hardware_profile is not None
            ):
                trial_runtime_est = estimate_runtime_overhead(
                    backend=baseline_context.backend_profile,
                    hardware=baseline_context.hardware_profile,
                    resident_weight_bytes=baseline_context.current_weight_estimate.total_bytes,
                    parameter_count=baseline_context.model.parameter_count,
                    graph_capture_enabled=False,
                )

        # 2. Assess feasibility for trial candidate
        trial_report = assess_memory_feasibility(
            weights=trial_weight_est,
            kv_cache=trial_kv_est,
            runtime_overhead=trial_runtime_est,
            hardware_budget=baseline_context.hardware_budget,
        )

    except Exception as exc:
        cand_id = _generate_candidate_id(proposal)
        return None, RejectedRecommendationCandidate(
            candidate_id=cand_id,
            action=action,
            reason_code="RECOMPUTE_FAILED",
            explanation=f"Re-computation of candidate parameters failed: {exc}",
            changes=proposal.changes,
        )

    cand_id = _generate_candidate_id(proposal)

    # 3. Calculate memory savings & impact
    baseline_req = baseline_report.aggregation.total_requirement
    candidate_req = trial_report.aggregation.total_requirement

    if baseline_req is None or candidate_req is None:
        return None, RejectedRecommendationCandidate(
            candidate_id=cand_id,
            action=action,
            reason_code="CANDIDATE_ESTIMATE_PARTIAL",
            explanation=(
                "Candidate memory requirement could not be completely aggregated."
            ),
            changes=proposal.changes,
        )

    savings = calculate_memory_savings(before=baseline_req, after=candidate_req)

    budget = baseline_context.hardware_budget
    before_headroom = subtract_byte_ranges(budget.recommended_allocatable, baseline_req)
    after_headroom = subtract_byte_ranges(budget.recommended_allocatable, candidate_req)

    before_status = baseline_report.feasibility.internal_status
    after_status = trial_report.feasibility.internal_status

    # 4. Filter acceptance / rejection criteria
    if savings.expected_bytes <= 0:
        return None, RejectedRecommendationCandidate(
            candidate_id=cand_id,
            action=action,
            reason_code="NO_MEMORY_IMPROVEMENT",
            explanation=(
                f"Expected memory savings ({savings.expected_bytes} bytes) "
                "are not positive."
            ),
            changes=proposal.changes,
        )

    before_rank = INTERNAL_STATUS_RISK_RANK.get(before_status, 99)
    after_rank = INTERNAL_STATUS_RISK_RANK.get(after_status, 99)

    if after_rank > before_rank:
        return None, RejectedRecommendationCandidate(
            candidate_id=cand_id,
            action=action,
            reason_code="STATUS_NOT_IMPROVED",
            explanation=(
                f"Candidate feasibility status ({after_status.value}) is worse "
                f"than baseline status ({before_status.value})."
            ),
            changes=proposal.changes,
        )

    strength = _determine_candidate_strength(
        before_status=before_status,
        after_status=after_status,
        eligibility=eligibility,
        action=action,
    )

    impact = CandidateMemoryImpact(
        before_requirement=baseline_req,
        after_requirement=candidate_req,
        savings=savings,
        before_headroom_recommended=before_headroom,
        after_headroom_recommended=after_headroom,
        before_status=before_status,
        after_status=after_status,
    )

    candidate = RecommendationCandidate(
        candidate_id=cand_id,
        action=action,
        strength=strength,
        title=proposal.title,
        explanation=proposal.explanation,
        changes=proposal.changes,
        impact=impact,
        eligibility=eligibility,
        confidence=trial_report.feasibility.confidence,
        source_constraint_codes=proposal.source_constraint_codes,
        tradeoff_severity=proposal.tradeoff_severity,
        tradeoffs=proposal.tradeoffs,
        verification_status=CandidateVerificationStatus.VERIFIED,
    )

    return candidate, None


def _generate_candidate_id(proposal: CandidateChangeProposal) -> str:
    """Generate a stable, deterministic candidate ID string."""
    if proposal.action == RecommendationAction.REDUCE_CONTEXT_LENGTH:
        val = proposal.changes[0].after
        return f"reduce-context-to-{val}"
    if proposal.action == RecommendationAction.REDUCE_ACTIVE_SEQUENCES:
        val = proposal.changes[0].after
        return f"reduce-active-sequences-to-{val}"
    if proposal.action == RecommendationAction.CHANGE_KV_DTYPE:
        before = str(proposal.changes[0].before).lower()
        after = str(proposal.changes[0].after).lower()
        return f"change-kv-dtype-{before}-to-{after}"
    if proposal.action == RecommendationAction.CHANGE_WEIGHT_DTYPE:
        before = str(proposal.changes[0].before).lower()
        after = str(proposal.changes[0].after).lower()
        return f"change-weight-dtype-{before}-to-{after}"
    if proposal.action == RecommendationAction.DISABLE_GRAPH_CAPTURE:
        return "disable-graph-capture"
    return "candidate-proposal"
