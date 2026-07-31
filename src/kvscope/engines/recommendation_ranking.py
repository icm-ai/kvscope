"""Engine for deterministic candidate ranking."""

from kvscope.domain.enums import InternalFeasibilityStatus
from kvscope.domain.recommendation import (
    CandidateVerificationStatus,
    RecommendationAction,
    RecommendationCandidate,
    RecommendationEligibility,
    RecommendationPolicy,
    RecommendationStrength,
    TradeoffSeverity,
)

STRENGTH_RANK: dict[RecommendationStrength, int] = {
    RecommendationStrength.REQUIRED: 0,
    RecommendationStrength.STRONG: 1,
    RecommendationStrength.CONDITIONAL: 2,
    RecommendationStrength.ADVISORY: 3,
    RecommendationStrength.INFORMATIONAL: 4,
}

ELIGIBILITY_RANK: dict[RecommendationEligibility, int] = {
    RecommendationEligibility.ELIGIBLE: 0,
    RecommendationEligibility.ADVISORY_ONLY: 1,
    RecommendationEligibility.INELIGIBLE: 2,
}

TRADEOFF_RANK: dict[TradeoffSeverity, int] = {
    TradeoffSeverity.NONE: 0,
    TradeoffSeverity.LOW: 1,
    TradeoffSeverity.MEDIUM: 2,
    TradeoffSeverity.HIGH: 3,
    TradeoffSeverity.UNKNOWN: 4,
}

STATUS_RANK: dict[InternalFeasibilityStatus, int] = {
    InternalFeasibilityStatus.GUARANTEED_FEASIBLE: 0,
    InternalFeasibilityStatus.EXPECTED_FEASIBLE: 1,
    InternalFeasibilityStatus.CONDITIONAL_FEASIBLE: 2,
    InternalFeasibilityStatus.HEADROOM_EXCEEDED: 3,
    InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED: 4,
    InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED: 5,
    InternalFeasibilityStatus.UNKNOWN: 99,
}

ACTION_RANK: dict[RecommendationAction, int] = {
    RecommendationAction.REDUCE_CONTEXT_LENGTH: 0,
    RecommendationAction.REDUCE_ACTIVE_SEQUENCES: 1,
    RecommendationAction.CHANGE_KV_DTYPE: 2,
    RecommendationAction.CHANGE_WEIGHT_DTYPE: 3,
    RecommendationAction.DISABLE_GRAPH_CAPTURE: 4,
    RecommendationAction.NO_CHANGE_REQUIRED: 5,
    RecommendationAction.PROVIDE_QUANTIZATION_METADATA: 6,
    RecommendationAction.PROVIDE_BACKEND_VERSION: 7,
    RecommendationAction.CALIBRATE_RUNTIME_OVERHEAD: 8,
    RecommendationAction.COMPLETE_ESTIMATE_REQUIRED: 9,
}


def _ranking_key(
    cand: RecommendationCandidate,
) -> tuple[int, int, int, int, int, int, int, int, int, str]:
    """Generate a multi-key tuple for deterministic sorting."""

    # 1. Target Reached
    target_reached = False
    if cand.impact is not None:
        target_reached = cand.impact.after_status in (
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
        )
    target_key = 0 if target_reached else 1

    # 2. Risk Status Rank
    after_status_rank = 99
    if cand.impact is not None:
        after_status_rank = STATUS_RANK.get(cand.impact.after_status, 99)

    # 3. Strength Rank
    strength_key = STRENGTH_RANK.get(cand.strength, 99)

    # 4. Eligibility Rank
    eligibility_key = ELIGIBILITY_RANK.get(cand.eligibility, 99)

    # 5. Tradeoff Rank
    tradeoff_key = TRADEOFF_RANK.get(cand.tradeoff_severity, 99)

    # 6. Guaranteed Savings Positive
    guaranteed_pos_key = 0
    if cand.impact is not None and cand.impact.savings.lower_bytes > 0:
        guaranteed_pos_key = -1

    # 7. Expected Savings Descending
    expected_savings_key = 0
    if cand.impact is not None:
        expected_savings_key = -cand.impact.savings.expected_bytes

    # 8. Parameter Change Magnitude (smaller change preferred)
    param_change_magnitude = 0
    if cand.changes:
        chg = cand.changes[0]
        if isinstance(chg.before, int) and isinstance(chg.after, int):
            param_change_magnitude = abs(chg.before - chg.after)

    # 9. Action Rank
    action_key = ACTION_RANK.get(cand.action, 99)

    # 10. Candidate ID
    id_key = cand.candidate_id

    return (
        target_key,
        after_status_rank,
        strength_key,
        eligibility_key,
        tradeoff_key,
        guaranteed_pos_key,
        expected_savings_key,
        param_change_magnitude,
        action_key,
        id_key,
    )


def rank_recommendation_candidates(
    candidates: list[RecommendationCandidate],
    policy: RecommendationPolicy,
) -> list[RecommendationCandidate]:
    """Rank candidates deterministically using multi-key tuple ordering."""

    verified_candidates = [
        c
        for c in candidates
        if c.verification_status != CandidateVerificationStatus.REJECTED
    ]
    return sorted(verified_candidates, key=_ranking_key)
