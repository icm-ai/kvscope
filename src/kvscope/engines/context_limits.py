"""Engine for back-solving safe context length limits."""

from kvscope.calculators.kv_cache import calculate_kv_cache, estimate_kv_cache
from kvscope.domain.enums import InternalFeasibilityStatus
from kvscope.domain.recommendation import (
    ContextLimitResult,
    RecommendationContext,
    RecommendationPolicy,
)
from kvscope.engines.analysis import assess_memory_feasibility


def _solve_and_verify_context_limit(
    *,
    kv_budget_bytes: int,
    bytes_per_token_all_seqs: int,
    fixed_tokens: int,
    block_size: int | None,
    min_context: int,
    max_context_clamp: int | None,
    target_statuses: set[InternalFeasibilityStatus],
    context: RecommendationContext,
) -> int | None:
    """Solve for context length given a KV budget and verify via forward engines."""
    if kv_budget_bytes <= 0 or bytes_per_token_all_seqs <= 0:
        return None

    max_allocated_tokens = kv_budget_bytes // bytes_per_token_all_seqs
    if block_size is not None and block_size > 0:
        aligned_tokens = (max_allocated_tokens // block_size) * block_size
    else:
        aligned_tokens = max_allocated_tokens

    candidate_context = aligned_tokens - fixed_tokens
    if max_context_clamp is not None:
        candidate_context = min(candidate_context, max_context_clamp)

    if candidate_context < min_context:
        return None

    step = block_size if (block_size is not None and block_size > 0) else 1
    max_iterations = 100
    iterations = 0

    while candidate_context >= min_context and iterations < max_iterations:
        iterations += 1
        # Copy inference config with trial context length
        trial_config = context.inference_config.model_copy(
            update={"context_length": candidate_context}
        )

        try:
            if context.backend_profile is not None:
                trial_kv = estimate_kv_cache(
                    model=context.model,
                    config=trial_config,
                    backend=context.backend_profile.to_spec(),
                )
            else:
                # Fallback to formula inputs replace
                inputs = context.current_kv_estimate.formula_inputs
                updated_inputs = type(inputs)(
                    num_hidden_layers=inputs.num_hidden_layers,
                    num_attention_heads=inputs.num_attention_heads,
                    num_key_value_heads=inputs.num_key_value_heads,
                    head_dim=inputs.head_dim,
                    context_tokens=candidate_context,
                    prefix_tokens=inputs.prefix_tokens,
                    multimodal_tokens=inputs.multimodal_tokens,
                    active_sequences=inputs.active_sequences,
                    kv_dtype=inputs.kv_dtype,
                    bytes_per_element=inputs.bytes_per_element,
                    block_size=inputs.block_size,
                    active_sequences_source=inputs.active_sequences_source,
                    prefix_shared=inputs.prefix_shared,
                )
                trial_kv = calculate_kv_cache(updated_inputs)

            report = assess_memory_feasibility(
                weights=context.current_weight_estimate,
                kv_cache=trial_kv,
                runtime_overhead=context.current_runtime_estimate,
                hardware_budget=context.hardware_budget,
            )

            if report.feasibility.internal_status in target_statuses:
                return candidate_context

        except Exception:
            pass

        candidate_context -= step

    return None


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

    weight_upper = context.current_weight_estimate.total_bytes
    weight_expected = context.current_weight_estimate.total_bytes

    runtime_upper = context.current_runtime_estimate.total_runtime_overhead.upper_bytes
    runtime_expected = (
        context.current_runtime_estimate.total_runtime_overhead.expected_bytes
    )
    budget = context.hardware_budget

    guaranteed_budget = (
        budget.recommended_allocatable.lower_bytes - weight_upper - runtime_upper
    )
    expected_budget = (
        budget.recommended_allocatable.expected_bytes
        - weight_expected
        - runtime_expected
    )
    ceiling_budget = (
        budget.allocatable_before_headroom.expected_bytes
        - weight_expected
        - runtime_expected
    )

    max_clamp = workload.model_max_context_length
    min_ctx = workload.minimum_context_length

    guaranteed_ctx = _solve_and_verify_context_limit(
        kv_budget_bytes=guaranteed_budget,
        bytes_per_token_all_seqs=bytes_per_token_all_seqs,
        fixed_tokens=fixed_tokens,
        block_size=block_size,
        min_context=min_ctx,
        max_context_clamp=max_clamp,
        target_statuses={InternalFeasibilityStatus.GUARANTEED_FEASIBLE},
        context=context,
    )

    expected_ctx = _solve_and_verify_context_limit(
        kv_budget_bytes=expected_budget,
        bytes_per_token_all_seqs=bytes_per_token_all_seqs,
        fixed_tokens=fixed_tokens,
        block_size=block_size,
        min_context=min_ctx,
        max_context_clamp=max_clamp,
        target_statuses={
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
        },
        context=context,
    )

    ceiling_ctx = _solve_and_verify_context_limit(
        kv_budget_bytes=ceiling_budget,
        bytes_per_token_all_seqs=bytes_per_token_all_seqs,
        fixed_tokens=fixed_tokens,
        block_size=block_size,
        min_context=min_ctx,
        max_context_clamp=max_clamp,
        target_statuses={
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
            InternalFeasibilityStatus.CONDITIONAL_FEASIBLE,
        },
        context=context,
    )

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
