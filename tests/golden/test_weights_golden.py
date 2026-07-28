"""Hand-calculated golden cases for model-weight sizing."""

from kvscope.calculators.weights import estimate_weight_memory
from kvscope.domain.dtypes import WeightDType


def test_one_billion_parameters_fp16_golden_case() -> None:
    result = estimate_weight_memory(1_000_000_000, dtype=WeightDType.FP16)

    # ceil(1,000,000,000 * 16 / 8) = 2,000,000,000 bytes.
    assert result.total_bytes == 2_000_000_000


def test_one_billion_parameters_int4_theoretical_lower_bound() -> None:
    result = estimate_weight_memory(1_000_000_000, dtype=WeightDType.INT4)

    # ceil(1,000,000,000 * 4 / 8) = 500,000,000 bytes.
    assert result.total_bytes == 500_000_000


def test_one_billion_parameters_groupwise_mixed_precision_golden_case() -> None:
    result = estimate_weight_memory(
        1_000_000_000,
        quantization_bits=4,
        quantized_parameter_count=900_000_000,
        group_size=128,
        scale_bytes_per_group=2,
        zero_point_bytes_per_group=1,
        unquantized_parameter_count=100_000_000,
        unquantized_dtype=WeightDType.FP16,
        alignment_bytes=256,
    )

    # Quantized: ceil(900,000,000 * 4 / 8) = 450,000,000.
    # Groups: ceil(900,000,000 / 128) = 7,031,250.
    # Scale: 7,031,250 * 2 = 14,062,500.
    # Zero-point: 7,031,250 * 1 = 7,031,250.
    # Unquantized FP16: 100,000,000 * 16 / 8 = 200,000,000.
    # Total: 450,000,000 + 14,062,500 + 7,031,250 + 200,000,000 + 256.
    assert result.total_bytes == 671_094_006
