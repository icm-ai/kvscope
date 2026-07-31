"""Engine for back-solving safe active sequence count limits."""

from kvscope.calculators.kv_cache import calculate_kv_cache, estimate_kv_cache
from kvscope.domain.enums import InternalFeasibilityStatus
from kvscope.domain.recommendation import (
    ActiveSequenceLimitResult,
    RecommendationContext,
    RecommendationPolicy,
)
from kvscope.engines.analysis import assess_memory_feasibility


def _solve_and_verify_sequence_limit(
    *,
    kv_budget_bytes: int,
    bytes_per_sequence: int,
    min_sequences: int,
    target_statuses: set[InternalFeasibilityStatus],
    context: RecommendationContext,
) -> int | None:
    """Solve active sequence count given a KV budget and verify via forward engines."""
    if kv_budget_bytes <= 0 or bytes_per_sequence <= 0:
        return None

    candidate_seqs = kv_budget_bytes // bytes_per_sequence
    if candidate_seqs < min_sequences:
        return None

    max_iterations = 100
    iterations = 0

    while candidate_seqs >= min_sequences and iterations < max_iterations:
        iterations += 1
        trial_config = context.inference_config.model_copy(
            update={
                "max_num_seqs": candidate_seqs,
                "active_sequences_override": candidate_seqs,
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
                inputs = context.current_kv_estimate.formula_inputs
                updated_inputs = type(inputs)(
                    num_hidden_layers=inputs.num_hidden_layers,
                    num_attention_heads=inputs.num_attention_heads,
                    num_key_value_heads=inputs.num_key_value_heads,
                    head_dim=inputs.head_dim,
                    context_tokens=inputs.context_tokens,
                    prefix_tokens=inputs.prefix_tokens,
                    multimodal_tokens=inputs.multimodal_tokens,
                    active_sequences=candidate_seqs,
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
                return candidate_seqs

        except Exception:
            pass

        candidate_seqs -= 1

    return None


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

    min_seqs = workload.minimum_active_sequences

    guaranteed_seqs = _solve_and_verify_sequence_limit(
        kv_budget_bytes=guaranteed_budget,
        bytes_per_sequence=bytes_per_seq,
        min_sequences=min_seqs,
        target_statuses={InternalFeasibilityStatus.GUARANTEED_FEASIBLE},
        context=context,
    )

    expected_seqs = _solve_and_verify_sequence_limit(
        kv_budget_bytes=expected_budget,
        bytes_per_sequence=bytes_per_seq,
        min_sequences=min_seqs,
        target_statuses={
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
        },
        context=context,
    )

    ceiling_seqs = _solve_and_verify_sequence_limit(
        kv_budget_bytes=ceiling_budget,
        bytes_per_sequence=bytes_per_seq,
        min_sequences=min_seqs,
        target_statuses={
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
            InternalFeasibilityStatus.CONDITIONAL_FEASIBLE,
        },
        context=context,
    )

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
