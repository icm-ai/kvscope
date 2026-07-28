"""Hand-checked golden cases for MHA, GQA, and MQA KV sizing."""

from kvscope.calculators.kv_cache import estimate_kv_cache
from kvscope.domain.backend import BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import Confidence
from kvscope.domain.model import ModelSpec


def make_model(*, layers: int, heads: int, kv_heads: int, head_dim: int) -> ModelSpec:
    """Build a model for a manually calculated golden case."""
    return ModelSpec(
        model_id="golden/model",
        architecture="golden",
        num_hidden_layers=layers,
        hidden_size=heads * head_dim,
        num_attention_heads=heads,
        num_key_value_heads=kv_heads,
        head_dim=head_dim,
        source="golden-test",
    )


def make_backend(block_size: int | None) -> BackendSpec:
    """Build a minimal backend profile for a golden case."""
    return BackendSpec(
        backend_id="golden-backend",
        base_overhead_bytes=0,
        overhead_per_billion_parameters_bytes=0,
        graph_capture_reserve_bytes=0,
        workspace_ratio=0.0,
        allocator_margin_ratio=0.0,
        kv_block_size=block_size,
        supports_kv_dtypes=[
            KVDType.FP32,
            KVDType.FP16,
            KVDType.BF16,
            KVDType.FP8,
            KVDType.INT8,
        ],
        supports_cpu_offload=False,
        confidence=Confidence.EXACT,
    )


def make_config(
    *,
    context: int,
    active_sequences: int,
    kv_dtype: KVDType,
    prefix: int = 0,
    multimodal: int = 0,
) -> InferenceConfig:
    """Build a workload for a golden case."""
    return InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=kv_dtype,
        context_length=context,
        batch_size=active_sequences,
        max_num_seqs=1,
        prefix_tokens=prefix,
        multimodal_tokens=multimodal,
    )


def test_mha_fp16_golden_case() -> None:
    """2 layers x 4 KV heads x 8 dim x FP16, 10 context tokens."""
    result = estimate_kv_cache(
        make_model(layers=2, heads=4, kv_heads=4, head_dim=8),
        make_config(context=10, active_sequences=1, kv_dtype=KVDType.FP16),
        make_backend(block_size=None),
    )

    # 2 * 2 * 10 * 1 * 4 * 8 * 2 = 2,560 bytes.
    assert result.raw_bytes == 2560
    assert result.allocated_bytes == 2560
    assert result.alignment_waste_bytes == 0


def test_gqa_fp16_golden_case() -> None:
    """24 layers x 8 KV heads x 128 dim x FP16, four sequences."""
    result = estimate_kv_cache(
        make_model(layers=24, heads=32, kv_heads=8, head_dim=128),
        make_config(context=4096, active_sequences=4, kv_dtype=KVDType.FP16),
        make_backend(block_size=16),
    )

    # 2 * 24 * 4096 * 4 * 8 * 128 * 2 = 1,610,612,736 bytes.
    assert result.raw_bytes == 1_610_612_736
    assert result.allocated_bytes == 1_610_612_736
    assert result.formula_inputs.attention_mode.value == "gqa"


def test_mqa_fp8_golden_case() -> None:
    """32 layers x 1 KV head x 128 dim x FP8, three sequences."""
    result = estimate_kv_cache(
        make_model(layers=32, heads=32, kv_heads=1, head_dim=128),
        make_config(
            context=2048,
            prefix=128,
            multimodal=64,
            active_sequences=3,
            kv_dtype=KVDType.FP8,
        ),
        make_backend(block_size=128),
    )

    # Raw: 2 * 32 * 2240 * 3 * 1 * 128 * 1 = 55,050,240 bytes.
    # 2,240 tokens align to 2,304; allocated = 56,623,104 bytes.
    assert result.raw_bytes == 55_050_240
    # Block aligned: 2304 allocated tokens * 8192 bytes/token
    # * 3 active sequences = 56,623,104 bytes.
    assert result.allocated_bytes == 56_623_104
    assert result.alignment_waste_bytes == 1_572_864
    assert result.formula_inputs.attention_mode.value == "mqa"


def test_int8_gqa_golden_case() -> None:
    """32 layers x 8 KV heads x 128 dim x INT8, 1 sequence, 100 tokens."""
    result = estimate_kv_cache(
        make_model(layers=32, heads=32, kv_heads=8, head_dim=128),
        make_config(context=100, active_sequences=1, kv_dtype=KVDType.INT8),
        make_backend(block_size=16),
    )
    # bytes_per_token = 2 * 32 * 8 * 128 * 1 = 65,536 bytes.
    # raw: 65,536 * 100 * 1 = 6,553,600 bytes.
    # aligned tokens = ceil(100/16)*16 = 112 tokens.
    # allocated: 65,536 * 112 = 7,340,032 bytes.
    assert result.raw_bytes == 6_553_600
    assert result.allocated_bytes == 7_340_032
    assert result.alignment_waste_bytes == 786_432


def test_fp32_mha_golden_case() -> None:
    """4 layers x 2 KV heads x 64 dim x FP32, 1 sequence, 10 tokens."""
    result = estimate_kv_cache(
        make_model(layers=4, heads=2, kv_heads=2, head_dim=64),
        make_config(context=10, active_sequences=1, kv_dtype=KVDType.FP32),
        make_backend(block_size=None),
    )
    # bytes_per_token = 2 * 4 * 2 * 64 * 4 = 4096 bytes.
    # raw = 4096 * 10 * 1 = 40,960 bytes.
    assert result.raw_bytes == 40_960
    assert result.allocated_bytes == 40_960

