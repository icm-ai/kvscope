"""Focused retreat-policy tests; public behavior is covered in recommendations."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_recommendations import _fixture_setup

from kvscope.api import find_safe_active_sequence_limits, find_safe_context_limits
from kvscope.domain.dtypes import KVDType
from kvscope.domain.enums import InternalFeasibilityStatus
from kvscope.domain.ranges import ByteRange
from kvscope.domain.recommendation import RecommendationContext, RecommendationPolicy
from kvscope.engines import safe_limit_verification as verifier


def _context() -> RecommendationContext:
    model, hardware, backend, config, weights, kv, runtime, budget = _fixture_setup()
    return RecommendationContext(
        model=model,
        inference_config=config,
        current_weight_estimate=weights,
        current_kv_estimate=kv,
        current_runtime_estimate=runtime,
        hardware_budget=budget,
        backend_profile=backend,
        hardware_profile=hardware,
    )


def _report(status: InternalFeasibilityStatus) -> SimpleNamespace:
    return SimpleNamespace(
        feasibility=SimpleNamespace(internal_status=status)
    )


def _request(
    axis: verifier.LimitAxis,
    initial: int,
    decrement: int,
    minimum: int = 1,
) -> verifier.VerificationRequest:
    return verifier.VerificationRequest(
        axis=axis,
        initial_candidate=initial,
        minimum_candidate=minimum,
        decrement=decrement,
        tier=verifier.BudgetTier.GUARANTEED,
        budgets=verifier.AvailableKVBudgets(100, 100, 100),
    )


def test_first_candidate_success_requires_exactly_one_assessment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def assess(**kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return _report(InternalFeasibilityStatus.GUARANTEED_FEASIBLE)

    monkeypatch.setattr(verifier, "assess_memory_feasibility", assess)
    result = verifier.solve_and_verify(
        context=_context(),
        request=_request(verifier.LimitAxis.ACTIVE_SEQUENCES, 5, 1),
    )
    assert result.candidate == 5
    assert calls == 1


def test_context_axis_retries_by_block_size_and_accepts_second_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context()
    seen_tokens: list[int] = []
    seen_configs = []
    original_estimate = verifier.estimate_kv_cache
    statuses = iter(
        [
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        ]
    )

    def assess(**kwargs: object) -> SimpleNamespace:
        kv = kwargs["kv_cache"]
        seen_tokens.append(kv.formula_inputs.context_tokens)
        return _report(next(statuses))

    def estimate(**kwargs: object) -> object:
        seen_configs.append(kwargs["config"])
        return original_estimate(**kwargs)

    monkeypatch.setattr(verifier, "estimate_kv_cache", estimate)
    monkeypatch.setattr(verifier, "assess_memory_feasibility", assess)
    result = verifier.solve_and_verify(
        context=ctx,
        request=_request(verifier.LimitAxis.CONTEXT_LENGTH, 512, 16),
    )
    assert result.candidate == 496
    assert seen_tokens == [512, 496]
    assert seen_configs == [
        ctx.inference_config.model_copy(update={"context_length": value})
        for value in (512, 496)
    ]


@pytest.mark.parametrize(
    ("axis", "candidate"),
    [
        (verifier.LimitAxis.CONTEXT_LENGTH, 777),
        (verifier.LimitAxis.ACTIVE_SEQUENCES, 3),
    ],
)
def test_formula_fallback_replaces_only_the_selected_axis(
    monkeypatch: pytest.MonkeyPatch,
    axis: verifier.LimitAxis,
    candidate: int,
) -> None:
    ctx = _context().model_copy(update={"backend_profile": None})
    source = replace(
        ctx.current_kv_estimate.formula_inputs,
        prefix_shared=True,
        active_sequences_source="batch_size",
    )
    ctx = ctx.model_copy(
        update={
            "current_kv_estimate": replace(
                ctx.current_kv_estimate, formula_inputs=source
            )
        }
    )
    captured = []
    original_calculate = verifier.calculate_kv_cache

    def calculate(inputs: object) -> object:
        captured.append(inputs)
        return original_calculate(inputs)

    monkeypatch.setattr(verifier, "calculate_kv_cache", calculate)
    monkeypatch.setattr(
        verifier,
        "assess_memory_feasibility",
        lambda **kwargs: _report(InternalFeasibilityStatus.GUARANTEED_FEASIBLE),
    )
    if axis is verifier.LimitAxis.CONTEXT_LENGTH:
        target = replace(source, context_tokens=candidate)
    else:
        target = replace(source, active_sequences=candidate)
    request = _request(axis, candidate, 1)
    result = verifier.solve_and_verify(context=ctx, request=request)
    assert result.candidate == candidate
    assert captured == [target]
    assert ctx.current_kv_estimate.formula_inputs == source


def test_sequential_axes_dtype_and_context_do_not_share_trial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context().model_copy(update={"backend_profile": None})
    first_inputs = replace(ctx.current_kv_estimate.formula_inputs, prefix_shared=True)
    ctx = ctx.model_copy(
        update={
            "current_kv_estimate": replace(
                ctx.current_kv_estimate, formula_inputs=first_inputs
            )
        }
    )
    second_inputs = replace(
        first_inputs,
        context_tokens=2048,
        kv_dtype=KVDType.FP8,
        bytes_per_element=1,
    )
    second_context = ctx.model_copy(
        update={
            "inference_config": ctx.inference_config.model_copy(
                update={"context_length": 2048, "kv_dtype": KVDType.FP8}
            ),
            "current_kv_estimate": replace(
                ctx.current_kv_estimate, formula_inputs=second_inputs
            ),
        }
    )
    captured = []
    original_calculate = verifier.calculate_kv_cache

    def calculate(inputs: object) -> object:
        captured.append(inputs)
        return original_calculate(inputs)

    monkeypatch.setattr(verifier, "calculate_kv_cache", calculate)
    monkeypatch.setattr(
        verifier,
        "assess_memory_feasibility",
        lambda **kwargs: _report(InternalFeasibilityStatus.GUARANTEED_FEASIBLE),
    )
    first_result = verifier.solve_and_verify(
        context=ctx,
        request=_request(verifier.LimitAxis.CONTEXT_LENGTH, 777, 1),
    )
    second_result = verifier.solve_and_verify(
        context=second_context,
        request=_request(verifier.LimitAxis.ACTIVE_SEQUENCES, 3, 1),
    )
    assert first_result.candidate == 777
    assert second_result.candidate == 3
    assert captured == [
        replace(first_inputs, context_tokens=777),
        replace(second_inputs, active_sequences=3),
    ]
    assert ctx.current_kv_estimate.formula_inputs == first_inputs
    assert second_context.current_kv_estimate.formula_inputs == second_inputs


def test_sequence_axis_retries_one_and_updates_both_config_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context()
    seen_config: list[tuple[int, int | None]] = []
    seen_configs = []
    statuses = iter(
        [
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
            InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        ]
    )
    original_estimate = verifier.estimate_kv_cache

    def estimate(**kwargs: object) -> object:
        config = kwargs["config"]
        seen_config.append(
            (config.max_num_seqs, config.active_sequences_override)
        )
        seen_configs.append(config)
        return original_estimate(**kwargs)

    def assess(**kwargs: object) -> SimpleNamespace:
        return _report(next(statuses))

    monkeypatch.setattr(verifier, "estimate_kv_cache", estimate)
    monkeypatch.setattr(verifier, "assess_memory_feasibility", assess)
    result = verifier.solve_and_verify(
        context=ctx,
        request=_request(verifier.LimitAxis.ACTIVE_SEQUENCES, 5, 1),
    )
    assert result.candidate == 4
    assert seen_config == [(5, 5), (4, 4)]
    assert seen_configs == [
        ctx.inference_config.model_copy(
            update={
                "max_num_seqs": value,
                "active_sequences_override": value,
            }
        )
        for value in (5, 4)
    ]


@pytest.mark.parametrize(
    ("axis", "initial", "step"),
    [
        (verifier.LimitAxis.CONTEXT_LENGTH, 4096, 16),
        (verifier.LimitAxis.ACTIVE_SEQUENCES, 150, 1),
    ],
)
def test_each_axis_stops_after_exactly_100_failed_verifications(
    monkeypatch: pytest.MonkeyPatch,
    axis: verifier.LimitAxis,
    initial: int,
    step: int,
) -> None:
    calls = 0

    def assess(**kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return _report(InternalFeasibilityStatus.EXPECTED_FEASIBLE)

    monkeypatch.setattr(verifier, "assess_memory_feasibility", assess)
    result = verifier.solve_and_verify(
        context=_context(), request=_request(axis, initial, step)
    )
    assert result.candidate is None
    assert calls == 100


def test_estimator_exception_is_caught_and_search_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original_estimate = verifier.estimate_kv_cache

    def estimate(**kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("narrow injected estimator failure")
        return original_estimate(**kwargs)

    monkeypatch.setattr(verifier, "estimate_kv_cache", estimate)
    monkeypatch.setattr(
        verifier,
        "assess_memory_feasibility",
        lambda **kwargs: _report(InternalFeasibilityStatus.GUARANTEED_FEASIBLE),
    )
    result = verifier.solve_and_verify(
        context=_context(),
        request=_request(verifier.LimitAxis.ACTIVE_SEQUENCES, 5, 1),
    )
    assert result.candidate == 4
    assert calls == 2


def test_hundredth_candidate_can_succeed_and_exception_does_not_end_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def assess(**kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("narrow injected assessment failure")
        if calls == 100:
            return _report(InternalFeasibilityStatus.GUARANTEED_FEASIBLE)
        return _report(InternalFeasibilityStatus.EXPECTED_FEASIBLE)

    monkeypatch.setattr(verifier, "assess_memory_feasibility", assess)
    result = verifier.solve_and_verify(
        context=_context(),
        request=_request(verifier.LimitAxis.ACTIVE_SEQUENCES, 150, 1),
    )
    assert result.candidate == 51
    assert calls == 100


@pytest.mark.parametrize(
    "axis",
    [verifier.LimitAxis.CONTEXT_LENGTH, verifier.LimitAxis.ACTIVE_SEQUENCES],
)
def test_public_interface_keeps_a_separate_100_attempt_budget_per_tier(
    monkeypatch: pytest.MonkeyPatch, axis: verifier.LimitAxis
) -> None:
    context = _context()
    weights = context.current_weight_estimate.total_bytes
    runtime = context.current_runtime_estimate.total_runtime_overhead
    if axis is verifier.LimitAxis.CONTEXT_LENGTH:
        unit_bytes = (
            2
            * context.model.num_hidden_layers
            * context.model.num_key_value_heads
            * context.model.head_dim
            * context.inference_config.kv_dtype.bytes_per_element
            * context.inference_config.active_sequences
        )
        targets = (5008, 10000, 15000)
        decrement = 16
    else:
        formula = context.current_kv_estimate.formula_inputs
        effective_tokens = (
            context.inference_config.context_length
            + context.inference_config.prefix_tokens
            + context.inference_config.multimodal_tokens
        )
        block_size = formula.block_size
        allocated_tokens = (
            ((effective_tokens + block_size - 1) // block_size) * block_size
            if block_size is not None and block_size > 0
            else effective_tokens
        )
        unit_bytes = (
            2
            * context.model.num_hidden_layers
            * allocated_tokens
            * context.model.num_key_value_heads
            * context.model.head_dim
            * context.inference_config.kv_dtype.bytes_per_element
        )
        targets = (500, 1000, 1500)
        decrement = 1
    guaranteed = weights + runtime.upper_bytes + unit_bytes * targets[0]
    expected = weights + runtime.expected_bytes + unit_bytes * targets[1]
    ceiling = weights + runtime.expected_bytes + unit_bytes * targets[2]
    budget = context.hardware_budget.model_copy(
        update={
            "recommended_allocatable": ByteRange(
                lower_bytes=guaranteed,
                expected_bytes=expected,
                upper_bytes=expected + unit_bytes * 100,
            ),
            "allocatable_before_headroom": ByteRange(
                lower_bytes=ceiling - unit_bytes * 100,
                expected_bytes=ceiling,
                upper_bytes=ceiling + unit_bytes * 100,
            ),
        }
    )
    context = context.model_copy(update={"hardware_budget": budget})
    candidates: list[int] = []

    def estimate(**kwargs: object) -> SimpleNamespace:
        config = kwargs["config"]
        candidate = (
            config.context_length
            if axis is verifier.LimitAxis.CONTEXT_LENGTH
            else config.max_num_seqs
        )
        return SimpleNamespace(candidate=candidate)

    def assess(**kwargs: object) -> SimpleNamespace:
        assert kwargs["weights"] is context.current_weight_estimate
        assert kwargs["runtime_overhead"] is context.current_runtime_estimate
        assert kwargs["hardware_budget"] is context.hardware_budget
        candidates.append(kwargs["kv_cache"].candidate)
        return _report(InternalFeasibilityStatus.UNKNOWN)

    monkeypatch.setattr(verifier, "estimate_kv_cache", estimate)
    monkeypatch.setattr(verifier, "assess_memory_feasibility", assess)
    if axis is verifier.LimitAxis.CONTEXT_LENGTH:
        result = find_safe_context_limits(
            context=context, policy=RecommendationPolicy()
        )
        assert all(
            value is None
            for value in (
                result.guaranteed_safe_max_context,
                result.expected_safe_max_context,
                result.allocatable_ceiling_max_context,
            )
        )
    else:
        result = find_safe_active_sequence_limits(
            context=context, policy=RecommendationPolicy()
        )
        assert all(
            value is None
            for value in (
                result.guaranteed_safe_max_sequences,
                result.expected_safe_max_sequences,
                result.allocatable_ceiling_max_sequences,
            )
        )
    assert len(candidates) == 300
    tier_attempts = [candidates[index : index + 100] for index in (0, 100, 200)]
    assert [len(attempts) for attempts in tier_attempts] == [100, 100, 100]
    tier_starts = [attempts[0] for attempts in tier_attempts]
    assert tier_starts == sorted(tier_starts)
    assert len(set(tier_starts)) == 3
    assert all(
        attempts[0] - attempts[-1] == decrement * 99
        for attempts in tier_attempts
    )


def test_minimum_boundary_is_verified_once_without_falling_below_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def assess(**kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return _report(InternalFeasibilityStatus.EXPECTED_FEASIBLE)

    monkeypatch.setattr(verifier, "assess_memory_feasibility", assess)
    result = verifier.solve_and_verify(
        context=_context(),
        request=_request(verifier.LimitAxis.ACTIVE_SEQUENCES, 1, 1, minimum=1),
    )
    assert result.candidate is None
    assert calls == 1
