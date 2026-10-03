"""Engine for back-solving safe context length limits."""

from kvscope.domain.recommendation import (
    ContextLimitResult,
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


def find_safe_context_limits(
    *,
    context: RecommendationContext,
    policy: RecommendationPolicy,
) -> ContextLimitResult:
    """Back-solve safe context length limits under budget targets."""

    cfg = context.inference_config
    model = context.model
    workload = context.workload_constraints

    fixed_tokens = cfg.prefix_tokens + cfg.multimodal_tokens
    block_size = context.current_kv_estimate.formula_inputs.block_size
    bytes_per_elem = cfg.kv_dtype.bytes_per_element

    bytes_per_token_all_seqs = (
        2
        * model.num_hidden_layers
        * model.num_key_value_heads
        * model.head_dim
        * bytes_per_elem
        * cfg.active_sequences
    )

    budgets = available_kv_budgets(context)
    max_clamp = workload.model_max_context_length
    min_ctx = workload.minimum_context_length

    def verified_limit(tier: BudgetTier) -> int | None:
        kv_budget = budgets.for_tier(tier)
        if kv_budget <= 0 or bytes_per_token_all_seqs <= 0:
            initial = min_ctx - 1
        else:
            max_allocated_tokens = kv_budget // bytes_per_token_all_seqs
            if block_size is not None and block_size > 0:
                aligned_tokens = (max_allocated_tokens // block_size) * block_size
            else:
                aligned_tokens = max_allocated_tokens
            initial = aligned_tokens - fixed_tokens
            if max_clamp is not None:
                initial = min(initial, max_clamp)
        result = solve_and_verify(
            context=context,
            request=VerificationRequest(
                axis=LimitAxis.CONTEXT_LENGTH,
                initial_candidate=initial,
                minimum_candidate=min_ctx,
                decrement=(
                    block_size if block_size is not None and block_size > 0 else 1
                ),
                tier=tier,
                budgets=budgets,
            ),
        )
        return result.candidate

    guaranteed_ctx = verified_limit(BudgetTier.GUARANTEED)
    expected_ctx = verified_limit(BudgetTier.EXPECTED)
    ceiling_ctx = verified_limit(BudgetTier.CEILING)

    assumptions = [
        "Fixed memory overheads (weights + runtime overhead) remain constant",
        "KV Cache scales linearly with total tokens across active sequences",
    ]
    warnings = []
    if ceiling_ctx is not None:
        warnings.append(
            "Allocatable ceiling max context bypasses system headroom reserves; "
            "do not use in production."
        )

    return ContextLimitResult(
        guaranteed_safe_max_context=guaranteed_ctx,
        expected_safe_max_context=expected_ctx,
        allocatable_ceiling_max_context=ceiling_ctx,
        current_context=cfg.context_length,
        fixed_tokens=fixed_tokens,
        block_size=block_size,
        limiting_budget=policy.target_budget.value,
        verified=True,
        assumptions=assumptions,
        warnings=warnings,
    )
