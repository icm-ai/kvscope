"""Engine for determining baseline recommendation eligibility."""

from kvscope.domain.enums import Confidence, InternalFeasibilityStatus
from kvscope.domain.recommendation import (
    RecommendationEligibility,
    RecommendationEligibilityResult,
)
from kvscope.domain.report import MemoryFeasibilityReport


def determine_recommendation_eligibility(
    report: MemoryFeasibilityReport,
) -> RecommendationEligibilityResult:
    """Determine baseline recommendation eligibility for a MemoryFeasibilityReport.

    Evaluation hierarchy:
    1. INELIGIBLE if partial, missing total requirement, or non-actionable.
    2. ADVISORY_ONLY if complete, but confidence is LOW or UNKNOWN.
    3. ELIGIBLE if complete, actionable, and confidence is MEDIUM or higher.
    """

    reason_codes: list[str] = []
    warnings: list[str] = []

    # 1. Ineligible checks
    if report.aggregation.is_partial:
        reason_codes.append("PARTIAL_MEMORY_ESTIMATE")
        warnings.append("Memory estimate is partial due to missing components.")
    if report.aggregation.total_requirement is None:
        reason_codes.append("MISSING_TOTAL_REQUIREMENT")
        warnings.append("Total memory requirement could not be aggregated.")
    if report.feasibility.internal_status == InternalFeasibilityStatus.UNKNOWN:
        reason_codes.append("UNKNOWN_FEASIBILITY")
        warnings.append("Internal feasibility status is UNKNOWN.")
    if not report.feasibility.is_actionable:
        reason_codes.append("INCOMPLETE_RUNTIME_PROFILE")
        warnings.append("Evaluation result is marked as non-actionable.")

    if reason_codes:
        return RecommendationEligibilityResult(
            eligibility=RecommendationEligibility.INELIGIBLE,
            reason_codes=reason_codes,
            confidence=report.feasibility.confidence,
            warnings=warnings,
        )

    # 2. Advisory-only checks
    if report.feasibility.confidence in (Confidence.LOW, Confidence.UNKNOWN):
        reason_codes.append("LOW_CONFIDENCE_ESTIMATE")
        warnings.append(
            "Feasibility estimate has LOW or UNKNOWN confidence; recommendations "
            "are advisory-only and require on-device validation."
        )
        return RecommendationEligibilityResult(
            eligibility=RecommendationEligibility.ADVISORY_ONLY,
            reason_codes=reason_codes,
            confidence=report.feasibility.confidence,
            warnings=warnings,
        )

    # 3. Eligible
    return RecommendationEligibilityResult(
        eligibility=RecommendationEligibility.ELIGIBLE,
        reason_codes=[],
        confidence=report.feasibility.confidence,
        warnings=[],
    )
