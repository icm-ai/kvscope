"""Shared back-solving budget and forward-verification policy."""

from dataclasses import dataclass, replace
from enum import Enum

from kvscope.calculators.kv_cache import calculate_kv_cache, estimate_kv_cache
from kvscope.domain.enums import InternalFeasibilityStatus
from kvscope.domain.recommendation import RecommendationContext
from kvscope.engines.analysis import assess_memory_feasibility


class LimitAxis(Enum):
    """The finite set of workload axes supported by safe-limit solving."""

    CONTEXT_LENGTH = "context_length"
    ACTIVE_SEQUENCES = "active_sequences"


class BudgetTier(Enum):
    """Safe-limit budget and acceptance policy tiers."""

    GUARANTEED = "guaranteed"
    EXPECTED = "expected"
    CEILING = "ceiling"


@dataclass(frozen=True)
class AvailableKVBudgets:
    """KV byte budgets after fixed resident weights and runtime overhead."""

    guaranteed_bytes: int
    expected_bytes: int
    ceiling_bytes: int

    def for_tier(self, tier: BudgetTier) -> int:
        """Return the exact integer budget associated with a tier."""
        if tier is BudgetTier.GUARANTEED:
            return self.guaranteed_bytes
        if tier is BudgetTier.EXPECTED:
            return self.expected_bytes
        return self.ceiling_bytes


@dataclass(frozen=True)
class VerificationRequest:
    """An axis-specific initial solution and bounded retreat policy."""

    axis: LimitAxis
    initial_candidate: int
    minimum_candidate: int
    decrement: int
    tier: BudgetTier
    budgets: AvailableKVBudgets


@dataclass(frozen=True)
class VerificationResult:
    """Candidate accepted by the forward verifier, or no valid candidate."""

    candidate: int | None


def available_kv_budgets(context: RecommendationContext) -> AvailableKVBudgets:
    """Compute guaranteed, expected, and ceiling KV budgets once."""
    weights = context.current_weight_estimate.total_bytes
    runtime = context.current_runtime_estimate.total_runtime_overhead
    budget = context.hardware_budget
    return AvailableKVBudgets(
        guaranteed_bytes=(
            budget.recommended_allocatable.lower_bytes
            - weights
            - runtime.upper_bytes
        ),
        expected_bytes=(
            budget.recommended_allocatable.expected_bytes
            - weights
            - runtime.expected_bytes
        ),
        ceiling_bytes=(
            budget.allocatable_before_headroom.expected_bytes
            - weights
            - runtime.expected_bytes
        ),
    )


def accepted_statuses(tier: BudgetTier) -> frozenset[InternalFeasibilityStatus]:
    """Return statuses accepted by one fixed safe-limit budget tier."""
    if tier is BudgetTier.GUARANTEED:
        return frozenset({InternalFeasibilityStatus.GUARANTEED_FEASIBLE})
    if tier is BudgetTier.EXPECTED:
        return frozenset(
            {
                InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
                InternalFeasibilityStatus.EXPECTED_FEASIBLE,
            }
        )
    return frozenset(
        {
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
            InternalFeasibilityStatus.CONDITIONAL_FEASIBLE,
        }
    )


def solve_and_verify(
    *, context: RecommendationContext, request: VerificationRequest
) -> VerificationResult:
    """Retreat from an algebraic solution until real forward verification accepts."""
    kv_budget = request.budgets.for_tier(request.tier)
    candidate = request.initial_candidate
    if kv_budget <= 0 or candidate < request.minimum_candidate:
        return VerificationResult(candidate=None)

    accepted = accepted_statuses(request.tier)
    for _ in range(100):
        # Keep construction outside the catch: invalid trial config behavior is stable.
        if request.axis is LimitAxis.CONTEXT_LENGTH:
            trial_config = context.inference_config.model_copy(
                update={"context_length": candidate}
            )

        else:
            trial_config = context.inference_config.model_copy(
                update={
                    "max_num_seqs": candidate,
                    "active_sequences_override": candidate,
                }
            )


        try:
            if context.backend_profile is not None:
                trial_kv = estimate_kv_cache(
                    model=context.model,
                    config=trial_config,
                    backend=context.backend_profile.to_spec(),
                )
            else:
                if request.axis is LimitAxis.CONTEXT_LENGTH:
                    inputs = replace(
                        context.current_kv_estimate.formula_inputs,
                        context_tokens=candidate,
                    )
                else:
                    inputs = replace(
                        context.current_kv_estimate.formula_inputs,
                        active_sequences=candidate,
                    )
                trial_kv = calculate_kv_cache(inputs)

            report = assess_memory_feasibility(
                weights=context.current_weight_estimate,
                kv_cache=trial_kv,
                runtime_overhead=context.current_runtime_estimate,
                hardware_budget=context.hardware_budget,
            )
            if report.feasibility.internal_status in accepted:
                return VerificationResult(candidate=candidate)
        except Exception:
            pass

        candidate -= request.decrement
        if candidate < request.minimum_candidate:
            break

    return VerificationResult(candidate=None)
