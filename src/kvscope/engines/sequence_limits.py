"""Engine for back-solving safe active sequence count limits."""

from kvscope.domain.recommendation import (
    ActiveSequenceLimitResult,
    RecommendationContext,
    RecommendationPolicy,
)
from kvscope.engines.safe_limit_verification import (
    BudgetTier,
    LimitAxis,
    VerificationRequest,
    available_kv_budgets,
    solve_and_verify,
)


def find_safe_active_sequence_limits(
    *,
    context: RecommendationContext,
    policy: RecommendationPolicy,
) -> ActiveSequenceLimitResult:
    """Back-solve safe active sequence count limits under budget targets."""

    cfg = context.inference_config
    model = context.model
    workload = context.workload_constraints

    block_size = context.current_kv_estimate.formula_inputs.block_size
    bytes_per_elem = cfg.kv_dtype.bytes_per_element

    eff_tokens = cfg.context_length + cfg.prefix_tokens + cfg.multimodal_tokens
    if block_size is not None and block_size > 0:
        alloc_tokens = ((eff_tokens + block_size - 1) // block_size) * block_size
    else:
        alloc_tokens = eff_tokens

    bytes_per_seq = (
        2
        * model.num_hidden_layers
        * alloc_tokens
        * model.num_key_value_heads
        * model.head_dim
        * bytes_per_elem
    )

    budgets = available_kv_budgets(context)
    min_seqs = workload.minimum_active_sequences

    def verified_limit(tier: BudgetTier) -> int | None:
        kv_budget = budgets.for_tier(tier)
        initial = (
            kv_budget // bytes_per_seq
            if kv_budget > 0 and bytes_per_seq > 0
            else min_seqs - 1
        )
        result = solve_and_verify(
            context=context,
            request=VerificationRequest(
                axis=LimitAxis.ACTIVE_SEQUENCES,
                initial_candidate=initial,
                minimum_candidate=min_seqs,
                decrement=1,
                tier=tier,
                budgets=budgets,
            ),
        )
        return result.candidate

    guaranteed_seqs = verified_limit(BudgetTier.GUARANTEED)
    expected_seqs = verified_limit(BudgetTier.EXPECTED)
    ceiling_seqs = verified_limit(BudgetTier.CEILING)

    assumptions = [
        "Fixed memory overheads (weights + runtime overhead) remain constant",
        "KV Cache scales linearly with total active sequences",
    ]
    warnings = []
    if ceiling_seqs is not None:
        warnings.append(
            "Allocatable ceiling max active sequences bypasses system headroom "
            "reserves; do not use in production."
        )

    return ActiveSequenceLimitResult(
        guaranteed_safe_max_sequences=guaranteed_seqs,
        expected_safe_max_sequences=expected_seqs,
        allocatable_ceiling_max_sequences=ceiling_seqs,
        current_active_sequences=cfg.active_sequences,
        effective_tokens_per_sequence=eff_tokens,
        controlling_parameter=cfg.active_sequences_source,
        verified=True,
        assumptions=assumptions,
        warnings=warnings,
    )
