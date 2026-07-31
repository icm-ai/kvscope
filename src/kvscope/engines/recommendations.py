"""Top-level recommendation engine orchestrator."""

from kvscope.domain.enums import InternalFeasibilityStatus, ProductFeasibilityStatus
from kvscope.domain.recommendation import (
    CandidateVerificationStatus,
    RecommendationAction,
    RecommendationCandidate,
    RecommendationContext,
    RecommendationEligibility,
    RecommendationPolicy,
    RecommendationReport,
    RecommendationStrength,
    RejectedRecommendationCandidate,
    SafeParameterLimits,
    TradeoffSeverity,
)
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.engines.candidate_evaluation import evaluate_candidate_proposal
from kvscope.engines.candidate_generation import generate_candidate_proposals
from kvscope.engines.context_limits import find_safe_context_limits
from kvscope.engines.recommendation_eligibility import (
    determine_recommendation_eligibility,
)
from kvscope.engines.recommendation_ranking import rank_recommendation_candidates
from kvscope.engines.sequence_limits import find_safe_active_sequence_limits


def generate_recommendations(
    *,
    context: RecommendationContext,
    baseline_report: MemoryFeasibilityReport,
    policy: RecommendationPolicy | None = None,
) -> RecommendationReport:
    """Generate structured recommendations and safe parameter capacity limits.

    Primary workflow:
    1. Determine recommendation eligibility from baseline report.
    2. Handle ineligible baselines with structured blocking actions.
    3. Back-solve safe context and active sequence limits.
    4. Handle already feasible baselines with NO_CHANGE_REQUIRED.
    5. Propose, evaluate via forward re-computation, rank, and package candidates.
    """
    pol = policy or RecommendationPolicy()
    eligibility_result = determine_recommendation_eligibility(baseline_report)

    # 1. Handle Ineligible Baselines
    if eligibility_result.eligibility == RecommendationEligibility.INELIGIBLE:
        primary_blocking = RecommendationCandidate(
            candidate_id="complete-estimate-required",
            action=RecommendationAction.COMPLETE_ESTIMATE_REQUIRED,
            strength=RecommendationStrength.ADVISORY,
            title="Complete memory estimate required before generating recommendations",
            explanation=(
                "Baseline memory feasibility assessment is partial or incomplete. "
                "Supply missing component estimates or runtime profiles before "
                "recommendations can be evaluated."
            ),
            changes=[],
            impact=None,
            eligibility=RecommendationEligibility.INELIGIBLE,
            confidence=eligibility_result.confidence,
            source_constraint_codes=eligibility_result.reason_codes,
            tradeoff_severity=TradeoffSeverity.NONE,
            tradeoffs=[],
            verification_status=CandidateVerificationStatus.ADVISORY_ONLY,
        )
        return RecommendationReport(
            schema_version="v0.1",
            eligibility=eligibility_result,
            baseline_report=baseline_report,
            primary_recommendation=primary_blocking,
            alternatives=[],
            rejected_candidates=[],
            safe_limits=None,
            combined_changes_may_be_required=False,
            assumptions=[
                "Recommendation generation was blocked due to partial or "
                "non-actionable baseline estimates."
            ],
            warnings=eligibility_result.warnings,
            evidence=[],
        )

    # 2. Back-solve Safe Parameter Limits
    context_limit = find_safe_context_limits(context=context, policy=pol)
    sequence_limit = find_safe_active_sequence_limits(context=context, policy=pol)
    safe_limits = SafeParameterLimits(
        context=context_limit,
        active_sequences=sequence_limit,
    )

    # 3. Handle Guaranteed Feasible Baselines
    internal_status = baseline_report.feasibility.internal_status
    if internal_status == InternalFeasibilityStatus.GUARANTEED_FEASIBLE:
        primary_no_change = RecommendationCandidate(
            candidate_id="no-change-required",
            action=RecommendationAction.NO_CHANGE_REQUIRED,
            strength=RecommendationStrength.INFORMATIONAL,
            title="Current configuration is guaranteed feasible",
            explanation=(
                "Current memory requirement is fully within recommended "
                "allocatable memory. No parameter modifications are required."
            ),
            changes=[],
            impact=None,
            eligibility=eligibility_result.eligibility,
            confidence=eligibility_result.confidence,
            source_constraint_codes=[],
            tradeoff_severity=TradeoffSeverity.NONE,
            tradeoffs=[],
            verification_status=CandidateVerificationStatus.VERIFIED,
        )
        return RecommendationReport(
            schema_version="v0.1",
            eligibility=eligibility_result,
            baseline_report=baseline_report,
            primary_recommendation=primary_no_change,
            alternatives=[],
            rejected_candidates=[],
            safe_limits=safe_limits,
            combined_changes_may_be_required=False,
            assumptions=[
                "Current workload configuration satisfies all memory budget thresholds."
            ],
            warnings=eligibility_result.warnings,
            evidence=[],
        )

    # 4. Generate & Evaluate Candidate Proposals
    proposals = generate_candidate_proposals(
        context=context,
        baseline_report=baseline_report,
        policy=pol,
        safe_context_limit=context_limit,
        safe_sequence_limit=sequence_limit,
    )

    accepted_candidates: list[RecommendationCandidate] = []
    rejected_candidates: list[RejectedRecommendationCandidate] = []

    for prop in proposals:
        cand, rej = evaluate_candidate_proposal(
            proposal=prop,
            baseline_context=context,
            baseline_report=baseline_report,
            policy=pol,
            eligibility=eligibility_result.eligibility,
        )
        if cand is not None:
            accepted_candidates.append(cand)
        if rej is not None:
            rejected_candidates.append(rej)

    # 5. Rank Candidates & Package Report
    ranked_candidates = rank_recommendation_candidates(accepted_candidates, pol)

    primary_rec: RecommendationCandidate | None = None
    alternatives: list[RecommendationCandidate] = []

    if ranked_candidates:
        primary_rec = ranked_candidates[0]
        alternatives = ranked_candidates[1 : pol.maximum_candidates]
    elif (
        baseline_report.feasibility.product_status == ProductFeasibilityStatus.FEASIBLE
    ):
        primary_rec = RecommendationCandidate(
            candidate_id="no-change-required",
            action=RecommendationAction.NO_CHANGE_REQUIRED,
            strength=RecommendationStrength.INFORMATIONAL,
            title="Current configuration is feasible",
            explanation=(
                "Current memory requirement is feasible without configuration changes."
            ),
            changes=[],
            impact=None,
            eligibility=eligibility_result.eligibility,
            confidence=eligibility_result.confidence,
            source_constraint_codes=[],
            tradeoff_severity=TradeoffSeverity.NONE,
            tradeoffs=[],
            verification_status=CandidateVerificationStatus.VERIFIED,
        )

    combined_required = False
    if primary_rec is not None and primary_rec.impact is not None:
        if primary_rec.impact.after_status not in (
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
        ):
            combined_required = True

    warnings = list(eligibility_result.warnings)
    if primary_rec is None:
        warnings.append(
            "No single-action candidate was sufficient to achieve feasible deployment; "
            "combined parameter modifications may be required."
        )
        combined_required = True

    return RecommendationReport(
        schema_version="v0.1",
        eligibility=eligibility_result,
        baseline_report=baseline_report,
        primary_recommendation=primary_rec,
        alternatives=alternatives,
        rejected_candidates=rejected_candidates,
        safe_limits=safe_limits,
        combined_changes_may_be_required=combined_required,
        assumptions=[
            "Candidate parameter changes were individually evaluated "
            "via forward engine re-computation."
        ],
        warnings=warnings,
        evidence=[],
    )
