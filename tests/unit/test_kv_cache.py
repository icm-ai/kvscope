"""Behavioral and property-based tests for the KV Cache Engine."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kvscope.calculators.kv_cache import (
    AttentionMode,
    KVCacheFormulaInputs,
    calculate_kv_cache,
    estimate_kv_cache,
)
from kvscope.domain.backend import BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import Confidence
from kvscope.domain.model import ModelSpec


def model(*, attention_heads: int = 4, kv_heads: int = 2) -> ModelSpec:
    """Build a small valid model for formula tests."""
    return ModelSpec(
        model_id="test/model",
        architecture="test",
        num_hidden_layers=2,
        hidden_size=attention_heads * 8,
        num_attention_heads=attention_heads,
        num_key_value_heads=kv_heads,
        head_dim=8,
        source="test",
    )


def backend(*, block_size: int | None = 8) -> BackendSpec:
    """Build a backend that supports both dtypes under test."""
    return BackendSpec(
        backend_id="test-backend",
        base_overhead_bytes=0,
        overhead_per_billion_parameters_bytes=0,
        graph_capture_reserve_bytes=0,
        workspace_ratio=0.0,
        allocator_margin_ratio=0.0,
        kv_block_size=block_size,
        supports_kv_dtypes=[KVDType.FP16, KVDType.FP8],
        supports_cpu_offload=False,
        confidence=Confidence.EXACT,
    )


def config(
    *,
    context: int = 10,
    batch_size: int = 1,
    kv_dtype: KVDType = KVDType.FP16,
    prefix: int = 0,
    multimodal: int = 0,
) -> InferenceConfig:
    """Build a valid workload configuration."""
    return InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=kv_dtype,
        context_length=context,
        batch_size=batch_size,
        max_num_seqs=1,
        prefix_tokens=prefix,
        multimodal_tokens=multimodal,
    )


def test_formula_result_contains_inputs_and_integer_byte_breakdown() -> None:
    result = estimate_kv_cache(
        model(attention_heads=4, kv_heads=2),
        config(context=10, batch_size=2, prefix=2, multimodal=1),
        backend(block_size=8),
    )

    assert result.formula_inputs.context_tokens == 10
    assert result.formula_inputs.prefix_tokens == 2
    assert result.formula_inputs.multimodal_tokens == 1
    assert result.formula_inputs.active_sequences == 2
    assert result.formula_inputs.effective_tokens == 13
    assert result.formula_inputs.allocated_tokens == 16
    assert result.effective_tokens == 13
    assert result.allocated_tokens == 16
    assert result.attention_mode.value == "gqa"
    assert result.raw_bytes == 3328
    assert result.allocated_bytes == 4096
    assert result.alignment_waste_bytes == 768
    assert result.bytes_per_token == 128
    assert result.bytes_per_sequence == 1664
    assert all(
        type(value) is int
        for value in (
            result.raw_bytes,
            result.allocated_bytes,
            result.alignment_waste_bytes,
            result.bytes_per_token,
            result.bytes_per_sequence,
        )
    )

    component = result.to_estimate_component()
    assert component.name == "kv_cache"
    assert component.bytes == 4096
    assert component.lower_bound_bytes == 3328
    assert component.upper_bound_bytes == 4096


@pytest.mark.parametrize(
    ("attention_heads", "kv_heads", "mode"),
    [(4, 4, "mha"), (4, 2, "gqa"), (4, 1, "mqa")],
)
def test_attention_layouts_use_kv_head_count(
    attention_heads: int, kv_heads: int, mode: str
) -> None:
    result = estimate_kv_cache(
        model(attention_heads=attention_heads, kv_heads=kv_heads),
        config(context=1, kv_dtype=KVDType.FP8),
        backend(block_size=None),
    )

    assert result.formula_inputs.attention_mode.value == mode
    assert result.bytes_per_token == 2 * 2 * kv_heads * 8


@given(
    context_a=st.integers(min_value=1, max_value=2048),
    context_delta=st.integers(min_value=0, max_value=2048),
)
def test_context_tokens_are_monotonic(context_a: int, context_delta: int) -> None:
    first = estimate_kv_cache(
        model(), config(context=context_a), backend(block_size=16)
    )
    second = estimate_kv_cache(
        model(), config(context=context_a + context_delta), backend(block_size=16)
    )

    assert second.raw_bytes >= first.raw_bytes
    assert second.allocated_bytes >= first.allocated_bytes


@given(
    active_a=st.integers(min_value=1, max_value=128),
    active_delta=st.integers(min_value=0, max_value=128),
)
def test_active_sequences_are_monotonic(active_a: int, active_delta: int) -> None:
    first = estimate_kv_cache(
        model(), config(batch_size=active_a), backend(block_size=16)
    )
    second = estimate_kv_cache(
        model(),
        config(batch_size=active_a + active_delta),
        backend(block_size=16),
    )

    assert second.raw_bytes >= first.raw_bytes
    assert second.allocated_bytes >= first.allocated_bytes


@given(
    context=st.integers(min_value=1, max_value=1000),
    prefix=st.integers(min_value=0, max_value=1000),
    multimodal=st.integers(min_value=0, max_value=1000),
    block_size=st.integers(min_value=1, max_value=64),
)
def test_block_alignment_is_ceil_and_waste_is_nonnegative(
    context: int, prefix: int, multimodal: int, block_size: int
) -> None:
    result = estimate_kv_cache(
        model(),
        config(context=context, prefix=prefix, multimodal=multimodal),
        backend(block_size=block_size),
    )
    inputs = result.formula_inputs

    assert inputs.allocated_tokens >= inputs.effective_tokens
    assert inputs.allocated_tokens % block_size == 0
    assert result.allocated_bytes >= result.raw_bytes
    assert result.alignment_waste_bytes == (result.allocated_bytes - result.raw_bytes)


def test_unaligned_block_size_none_returns_exact_raw_bytes() -> None:
    result = estimate_kv_cache(model(), config(context=100), backend(block_size=None))
    assert result.allocated_bytes == result.raw_bytes
    assert result.alignment_waste_bytes == 0


def test_fp8_uses_half_the_fp16_bytes() -> None:
    fp16 = estimate_kv_cache(
        model(), config(kv_dtype=KVDType.FP16), backend(block_size=None)
    )
    fp8 = estimate_kv_cache(
        model(), config(kv_dtype=KVDType.FP8), backend(block_size=None)
    )

    assert fp16.raw_bytes == 2 * fp8.raw_bytes
    assert fp16.allocated_bytes == 2 * fp8.allocated_bytes


def test_zero_context_with_positive_prefix_is_valid() -> None:
    result = calculate_kv_cache(
        KVCacheFormulaInputs(
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=0,
            prefix_tokens=100,
            multimodal_tokens=0,
            active_sequences=1,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=16,
        )
    )
    assert result.effective_tokens == 100
    assert result.allocated_tokens == 112  # ceil(100/16)*16
    assert result.raw_bytes == 128 * 100


def test_prefix_shared_calculates_prefix_memory_once() -> None:
    # 2 layers, 2 kv_heads, 8 head_dim, fp16 -> 128 bytes/token
    # context=10, prefix=100, active_sequences=4
    # unshared: context=10 * 4 seqs = 40 tokens
    # shared: prefix=100 * 1 = 100 tokens
    # total raw: 140 * 128 = 17920 bytes
    shared_result = calculate_kv_cache(
        KVCacheFormulaInputs(
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=10,
            prefix_tokens=100,
            multimodal_tokens=0,
            active_sequences=4,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=None,
            prefix_shared=True,
        )
    )
    unshared_result = calculate_kv_cache(
        KVCacheFormulaInputs(
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=10,
            prefix_tokens=100,
            multimodal_tokens=0,
            active_sequences=4,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=None,
            prefix_shared=False,
        )
    )
    assert shared_result.raw_bytes == 128 * (10 * 4 + 100)
    assert unshared_result.raw_bytes == 128 * (110 * 4)
    assert shared_result.raw_bytes < unshared_result.raw_bytes


@pytest.mark.parametrize(
    "inputs",
    [
        KVCacheFormulaInputs(
            num_hidden_layers=0,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=1,
            prefix_tokens=0,
            multimodal_tokens=0,
            active_sequences=1,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=None,
        ),
        KVCacheFormulaInputs(
            num_hidden_layers=1,
            num_attention_heads=3,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=1,
            prefix_tokens=0,
            multimodal_tokens=0,
            active_sequences=1,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=None,
        ),
        KVCacheFormulaInputs(
            num_hidden_layers=1,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=1,
            prefix_tokens=0,
            multimodal_tokens=0,
            active_sequences=1,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=0,
        ),
        KVCacheFormulaInputs(
            num_hidden_layers=1,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=1,
            prefix_tokens=0,
            multimodal_tokens=0,
            active_sequences=1,
            kv_dtype=KVDType.FP16,
            bytes_per_element=4,  # Mismatch with FP16 (2 bytes)
            block_size=None,
        ),
        KVCacheFormulaInputs(
            num_hidden_layers=1,
            num_attention_heads=2,
            num_key_value_heads=4,  # kv_heads > attention_heads
            head_dim=8,
            context_tokens=1,
            prefix_tokens=0,
            multimodal_tokens=0,
            active_sequences=1,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=None,
        ),
        KVCacheFormulaInputs(
            num_hidden_layers=1,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=0,
            prefix_tokens=0,
            multimodal_tokens=0,  # Zero total tokens
            active_sequences=1,
            kv_dtype=KVDType.FP16,
            bytes_per_element=2,
            block_size=None,
        ),
        KVCacheFormulaInputs(
            num_hidden_layers=1,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=8,
            context_tokens=1,
            prefix_tokens=0,
            multimodal_tokens=0,
            active_sequences=1,
            kv_dtype="invalid_type",  # Not a KVDType enum
            bytes_per_element=2,
            block_size=None,
        ),
    ],
)
def test_formula_rejects_illegal_parameters(
    inputs: KVCacheFormulaInputs,
) -> None:
    with pytest.raises(ValueError):
        calculate_kv_cache(inputs)


def test_engine_rejects_unsupported_kv_dtype() -> None:
    unsupported_backend = BackendSpec(
        backend_id="fp16-only",
        base_overhead_bytes=0,
        overhead_per_billion_parameters_bytes=0,
        graph_capture_reserve_bytes=0,
        workspace_ratio=0.0,
        allocator_margin_ratio=0.0,
        kv_block_size=None,
        supports_kv_dtypes=[KVDType.FP16],
        supports_cpu_offload=False,
        confidence=Confidence.EXACT,
    )

    with pytest.raises(ValueError, match="does not support KV dtype"):
        estimate_kv_cache(model(), config(kv_dtype=KVDType.FP8), unsupported_backend)


def test_kv_cache_estimate_properties_and_to_estimate_component() -> None:
    inputs = KVCacheFormulaInputs(
        num_hidden_layers=2,
        num_attention_heads=8,
        num_key_value_heads=4,
        head_dim=64,
        context_tokens=100,
        prefix_tokens=0,
        multimodal_tokens=0,
        active_sequences=1,
        kv_dtype=KVDType.FP16,
        bytes_per_element=2,
        block_size=16,
    )
    result = calculate_kv_cache(inputs)
    assert result.effective_tokens == 100
    assert result.allocated_tokens == 112
    assert result.attention_mode == AttentionMode.GQA
    component = result.to_estimate_component()
    assert component.name == "kv_cache"
    assert component.bytes == result.allocated_bytes


def test_prefix_shared_with_block_size_calculation() -> None:
    inputs = KVCacheFormulaInputs(
        num_hidden_layers=1,
        num_attention_heads=4,
        num_key_value_heads=4,
        head_dim=32,
        context_tokens=10,
        prefix_tokens=20,
        multimodal_tokens=5,
        prefix_shared=True,
        active_sequences=2,
        kv_dtype=KVDType.FP16,
        bytes_per_element=2,
        block_size=16,
    )
    result = calculate_kv_cache(inputs)
    assert result.allocated_bytes > 0


def test_formula_rejects_negative_token_counts() -> None:
    inputs = KVCacheFormulaInputs(
        num_hidden_layers=1,
        num_attention_heads=4,
        num_key_value_heads=4,
        head_dim=32,
        context_tokens=-5,
        prefix_tokens=0,
        multimodal_tokens=0,
        active_sequences=1,
        kv_dtype=KVDType.FP16,
        bytes_per_element=2,
        block_size=None,
    )
    msg = "context_tokens must be a non-negative integer"
    with pytest.raises(ValueError, match=msg):
        calculate_kv_cache(inputs)
