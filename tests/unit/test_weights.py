"""Unit and property-based tests for the Weight Engine."""

from decimal import Decimal
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kvscope.calculators.weights import (
    WeightEstimationMethod,
    WeightMemoryEstimate,
    estimate_weight_memory,
)
from kvscope.domain.dtypes import WeightDType
from kvscope.domain.enums import Confidence
from kvscope.domain.weight import WeightArtifactSummary
from kvscope.errors import InvalidModelConfigError


@pytest.mark.parametrize(
    ("dtype", "bits"),
    [
        (WeightDType.FP32, 32),
        (WeightDType.FP16, 16),
        (WeightDType.BF16, 16),
        (WeightDType.FP8, 8),
        (WeightDType.INT8, 8),
        (WeightDType.INT4, 4),
    ],
)
def test_parameter_count_mode_supports_all_named_dtypes(
    dtype: WeightDType, bits: int
) -> None:
    result = estimate_weight_memory(100, dtype=dtype)

    assert result.quantized_payload_bytes == 100 * bits // 8
    assert result.unquantized_payload_bytes == 0
    assert result.total_bytes == result.quantized_payload_bytes
    assert result.estimation_method is WeightEstimationMethod.PARAMETER_COUNT
    assert result.effective_bits_per_weight == bits


def test_custom_bits_and_sub_byte_payload_round_up() -> None:
    result = estimate_weight_memory(3, bits_per_weight=Decimal("1.5"))

    assert result.quantized_payload_bytes == 1
    assert result.total_bytes == 1
    assert result.effective_bits_per_weight == Fraction(8, 3)


def test_group_quantization_rounds_groups_and_adds_metadata() -> None:
    result = estimate_weight_memory(
        257,
        dtype=WeightDType.INT4,
        quantized_parameter_count=257,
        group_size=128,
        scale_bytes_per_group=2,
        zero_point_bytes_per_group=1,
    )

    assert result.quantized_payload_bytes == 129
    assert result.scale_overhead_bytes == 3 * 2
    assert result.zero_point_overhead_bytes == 3
    assert result.total_bytes == 138


def test_group_quantization_supports_partially_unquantized_fp16() -> None:
    result = estimate_weight_memory(
        1000,
        quantization_bits=4,
        quantized_parameter_count=900,
        group_size=128,
        scale_bytes_per_group=2,
        zero_point_bytes_per_group=1,
        unquantized_parameter_count=100,
        unquantized_dtype=WeightDType.FP16,
        alignment_bytes=7,
    )

    assert result.quantized_payload_bytes == 450
    assert result.unquantized_payload_bytes == 200
    assert result.scale_overhead_bytes == 16
    assert result.zero_point_overhead_bytes == 8
    assert result.alignment_overhead_bytes == 7
    assert result.total_bytes == 681


def test_alignment_boundary_is_applied_once() -> None:
    result = estimate_weight_memory(9, dtype=WeightDType.INT8, alignment=16)

    assert result.quantized_payload_bytes == 9
    assert result.alignment_overhead_bytes == 7
    assert result.total_bytes == 16


def test_artifact_summary_separates_storage_from_resident_estimate() -> None:
    artifact = WeightArtifactSummary(
        payload_bytes=1000,
        metadata_bytes=20,
        alignment_bytes=4,
    )
    result = estimate_weight_memory(artifact=artifact)

    assert result.estimation_method is WeightEstimationMethod.ARTIFACT_SUMMARY
    assert result.artifact_storage_bytes == 1024
    assert result.estimated_resident_weight_bytes == 1024
    assert result.total_bytes == 1024
    assert result.effective_bits_per_weight is None
    assert any("not a measurement" in warning for warning in result.warnings)


def test_result_converts_to_existing_estimate_component() -> None:
    component = estimate_weight_memory(
        10, dtype=WeightDType.FP16
    ).to_estimate_component()

    assert component.name == "weights"
    assert component.bytes == 20


@given(
    parameter_count=st.integers(min_value=1, max_value=10**6),
    delta=st.integers(min_value=0, max_value=10**6),
)
def test_parameter_count_is_monotonic(parameter_count: int, delta: int) -> None:
    first = estimate_weight_memory(parameter_count, dtype=WeightDType.INT4)
    second = estimate_weight_memory(parameter_count + delta, dtype=WeightDType.INT4)

    assert second.total_bytes >= first.total_bytes


@given(
    parameter_count=st.integers(min_value=1, max_value=10**5),
    bits_a=st.integers(min_value=1, max_value=64),
    bits_delta=st.integers(min_value=0, max_value=64),
)
def test_bits_per_weight_is_monotonic(
    parameter_count: int, bits_a: int, bits_delta: int
) -> None:
    first = estimate_weight_memory(parameter_count, bits_per_weight=bits_a)
    second = estimate_weight_memory(
        parameter_count, bits_per_weight=bits_a + bits_delta
    )

    assert second.total_bytes >= first.total_bytes


@given(
    fraction_a=st.integers(min_value=0, max_value=100),
    fraction_delta=st.integers(min_value=0, max_value=100),
)
def test_unquantized_fraction_is_monotonic(
    fraction_a: int, fraction_delta: int
) -> None:
    first = estimate_weight_memory(
        10_000,
        quantization_bits=4,
        group_size=128,
        unquantized_fraction=Decimal(fraction_a) / 100,
        unquantized_dtype=WeightDType.FP16,
    )
    second_fraction = min(fraction_a + fraction_delta, 100)
    second = estimate_weight_memory(
        10_000,
        quantization_bits=4,
        group_size=128,
        unquantized_fraction=Decimal(second_fraction) / 100,
        unquantized_dtype=WeightDType.FP16,
    )

    assert second.total_bytes >= first.total_bytes


@given(
    scale_a=st.integers(min_value=0, max_value=32),
    scale_delta=st.integers(min_value=0, max_value=32),
    zero_a=st.integers(min_value=0, max_value=32),
    zero_delta=st.integers(min_value=0, max_value=32),
)
def test_quantization_metadata_sizes_are_monotonic(
    scale_a: int, scale_delta: int, zero_a: int, zero_delta: int
) -> None:
    first = estimate_weight_memory(
        1000,
        dtype=WeightDType.INT4,
        group_size=128,
        scale_bytes_per_group=scale_a,
        zero_point_bytes_per_group=zero_a,
    )
    second = estimate_weight_memory(
        1000,
        dtype=WeightDType.INT4,
        group_size=128,
        scale_bytes_per_group=scale_a + scale_delta,
        zero_point_bytes_per_group=zero_a + zero_delta,
    )

    assert second.total_bytes >= first.total_bytes


@given(
    group_size_a=st.integers(min_value=1, max_value=1024),
    group_size_b=st.integers(min_value=1, max_value=1024),
)
def test_smaller_groups_do_not_reduce_metadata(
    group_size_a: int, group_size_b: int
) -> None:
    larger, smaller = max(group_size_a, group_size_b), min(group_size_a, group_size_b)
    first = estimate_weight_memory(
        10_000,
        dtype=WeightDType.INT4,
        group_size=larger,
        scale_bytes_per_group=2,
        zero_point_bytes_per_group=1,
    )
    second = estimate_weight_memory(
        10_000,
        dtype=WeightDType.INT4,
        group_size=smaller,
        scale_bytes_per_group=2,
        zero_point_bytes_per_group=1,
    )

    assert second.scale_overhead_bytes + second.zero_point_overhead_bytes >= (
        first.scale_overhead_bytes + first.zero_point_overhead_bytes
    )


@given(parameter_count=st.integers(min_value=1, max_value=10**6))
def test_legal_inputs_return_nonnegative_integer_bytes(parameter_count: int) -> None:
    result = estimate_weight_memory(
        parameter_count,
        quantization_bits=4,
        group_size=128,
        scale_bytes_per_group=2,
        zero_point_bytes_per_group=1,
    )

    fields = (
        result.quantized_payload_bytes,
        result.unquantized_payload_bytes,
        result.scale_overhead_bytes,
        result.zero_point_overhead_bytes,
        result.metadata_bytes,
        result.alignment_overhead_bytes,
        result.total_bytes,
    )
    assert all(type(value) is int and value >= 0 for value in fields)
    assert result.total_bytes == sum(fields[:-1])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"parameter_count": 0, "dtype": WeightDType.FP16}, "parameter_count"),
        ({"parameter_count": -1, "dtype": WeightDType.FP16}, "parameter_count"),
        ({"parameter_count": 1, "bits_per_weight": 0}, "bits_per_weight"),
        (
            {
                "parameter_count": 1,
                "quantization_bits": 4,
                "group_size": 0,
            },
            "group_size",
        ),
        (
            {
                "parameter_count": 10,
                "quantization_bits": 4,
                "group_size": 2,
                "quantized_parameter_count": -1,
            },
            "quantized_parameter_count",
        ),
        (
            {
                "parameter_count": 10,
                "quantization_bits": 4,
                "group_size": 2,
                "unquantized_parameter_count": -1,
            },
            "unquantized_parameter_count",
        ),
        (
            {
                "parameter_count": 10,
                "quantization_bits": 4,
                "group_size": 2,
                "unquantized_fraction": Decimal("1.1"),
            },
            "unquantized_fraction",
        ),
        (
            {
                "parameter_count": 10,
                "quantization_bits": 4,
                "group_size": 2,
                "scale_bytes_per_group": -1,
            },
            "scale_bytes_per_group",
        ),
        (
            {
                "parameter_count": 10,
                "quantization_bits": 4,
                "group_size": 2,
                "alignment": 0,
            },
            "alignment",
        ),
    ],
)
def test_invalid_inputs_raise_locatable_project_error(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidModelConfigError, match=message):
        estimate_weight_memory(**kwargs)


def test_conflicting_precision_and_count_inputs_are_rejected() -> None:
    with pytest.raises(InvalidModelConfigError, match="conflicts"):
        estimate_weight_memory(
            100,
            dtype=WeightDType.INT4,
            bits_per_weight=8,
        )

    with pytest.raises(InvalidModelConfigError, match="conflicts"):
        estimate_weight_memory(
            100,
            quantization_bits=4,
            group_size=16,
            quantized_parameter_count=80,
            unquantized_parameter_count=10,
            unquantized_fraction=Decimal("0.2"),
            unquantized_dtype=WeightDType.FP16,
        )

    with pytest.raises(InvalidModelConfigError, match="exceed"):
        estimate_weight_memory(
            100,
            quantization_bits=4,
            group_size=16,
            quantized_parameter_count=80,
            unquantized_parameter_count=30,
            unquantized_dtype=WeightDType.FP16,
        )

    with pytest.raises(InvalidModelConfigError, match="cannot be combined"):
        estimate_weight_memory(
            100,
            dtype=WeightDType.FP16,
            artifact=WeightArtifactSummary(payload_bytes=100),
        )


def test_group_size_larger_than_parameter_count_rounds_to_one_group() -> None:
    result = estimate_weight_memory(
        50,
        dtype=WeightDType.INT4,
        group_size=128,
        scale_bytes_per_group=2,
        zero_point_bytes_per_group=1,
    )
    assert result.scale_overhead_bytes == 2  # 1 group * 2 bytes
    assert result.zero_point_overhead_bytes == 1  # 1 group * 1 byte
    assert result.quantized_payload_bytes == 25  # ceil(50 * 4 / 8)
    assert result.total_bytes == 28


def test_empty_weight_artifact_summary_raises_error() -> None:
    msg = "artifact summary must contain at least one byte"
    with pytest.raises(ValueError, match=msg):
        WeightArtifactSummary(payload_bytes=0, metadata_bytes=0, alignment_bytes=0)


def test_weight_estimate_validation_errors() -> None:
    # Artifact invalid type
    msg1 = "must be a WeightArtifactSummary"
    with pytest.raises(InvalidModelConfigError, match=msg1):
        estimate_weight_memory(artifact="invalid_artifact")  # type: ignore[arg-type]

    # Non-finite float for bits
    msg2 = "must be a finite numeric value"
    with pytest.raises(InvalidModelConfigError, match=msg2):
        estimate_weight_memory(100, bits_per_weight=float("nan"))

    with pytest.raises(InvalidModelConfigError, match=msg2):
        estimate_weight_memory(100, bits_per_weight="invalid_bits")

    # Resolve bits invalid dtype or missing bits
    msg3 = "must be a WeightDType"
    with pytest.raises(InvalidModelConfigError, match=msg3):
        estimate_weight_memory(100, dtype="not_a_dtype")  # type: ignore[arg-type]

    msg4 = "must be supplied with dtype or custom bits"
    with pytest.raises(InvalidModelConfigError, match=msg4):
        estimate_weight_memory(100)

    # Unquantized dtype invalid type
    with pytest.raises(InvalidModelConfigError, match=msg3):
        estimate_weight_memory(
            100,
            dtype=WeightDType.FP16,
            unquantized_dtype="invalid",  # type: ignore[arg-type]
        )

    # Group mode with invalid dtype
    with pytest.raises(InvalidModelConfigError, match=msg3):
        estimate_weight_memory(100, group_size=32, dtype="not_a_dtype")  # type: ignore[arg-type]

    # Group mode with conflicting bits_per_weight and quantization_bits
    msg5 = "conflicts with bits_per_weight"
    with pytest.raises(InvalidModelConfigError, match=msg5):
        estimate_weight_memory(
            100, group_size=32, bits_per_weight=4, quantization_bits=8
        )

    # Group mode missing group_size
    msg6 = "must be supplied in group quantization mode"
    with pytest.raises(InvalidModelConfigError, match=msg6):
        estimate_weight_memory(100, quantization_bits=4, scale_bytes_per_group=2)

    # Quantized parameter count exceeds total parameter count
    msg7 = "must not exceed parameter_count"
    with pytest.raises(InvalidModelConfigError, match=msg7):
        estimate_weight_memory(
            100,
            quantization_bits=4,
            group_size=16,
            quantized_parameter_count=150,
        )

    # Unquantized parameters without unquantized_dtype
    msg9 = "must be supplied when unquantized parameters are present"
    with pytest.raises(InvalidModelConfigError, match=msg9):
        estimate_weight_memory(
            100,
            quantization_bits=4,
            group_size=16,
            unquantized_parameter_count=10,
        )

    # Float bits and matching bits_per_weight & quantization_bits
    res = estimate_weight_memory(
        100, bits_per_weight=4.0, quantization_bits=4.0, group_size=16
    )
    assert res.total_bytes > 0

    # Matching quantized_parameter_count and unquantized_parameter_count
    # covering total_parameters
    res_covered = estimate_weight_memory(
        100,
        quantization_bits=4,
        group_size=16,
        quantized_parameter_count=70,
        unquantized_parameter_count=30,
        unquantized_dtype=WeightDType.FP16,
    )
    assert res_covered.total_bytes > 0

    res_fraction = estimate_weight_memory(
        100,
        quantization_bits=4,
        group_size=16,
        quantized_parameter_count=70,
        unquantized_fraction="0.3",
        unquantized_dtype=WeightDType.FP16,
    )
    assert res_fraction.total_bytes > 0


def test_weight_memory_estimate_model_validators() -> None:
    msg1 = "must be a non-negative integer"
    with pytest.raises(ValueError, match=msg1):
        WeightMemoryEstimate(
            quantized_payload_bytes=-1,
            unquantized_payload_bytes=0,
            scale_overhead_bytes=0,
            zero_point_overhead_bytes=0,
            metadata_bytes=0,
            alignment_overhead_bytes=0,
            total_bytes=0,
            effective_bits_per_weight=Fraction(16, 1),
            estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
            confidence=Confidence.EXACT,
            assumptions=(),
            warnings=(),
        )

    msg2 = "total_bytes must equal all byte components combined"
    with pytest.raises(ValueError, match=msg2):
        WeightMemoryEstimate(
            quantized_payload_bytes=100,
            unquantized_payload_bytes=0,
            scale_overhead_bytes=0,
            zero_point_overhead_bytes=0,
            metadata_bytes=0,
            alignment_overhead_bytes=0,
            total_bytes=999,
            effective_bits_per_weight=Fraction(16, 1),
            estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
            confidence=Confidence.EXACT,
            assumptions=(),
            warnings=(),
        )

    msg3 = "effective_bits_per_weight must be positive or None"
    with pytest.raises(ValueError, match=msg3):
        WeightMemoryEstimate(
            quantized_payload_bytes=100,
            unquantized_payload_bytes=0,
            scale_overhead_bytes=0,
            zero_point_overhead_bytes=0,
            metadata_bytes=0,
            alignment_overhead_bytes=0,
            total_bytes=100,
            effective_bits_per_weight=Fraction(0, 1),
            estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
            confidence=Confidence.EXACT,
            assumptions=(),
            warnings=(),
        )

    msg4 = "artifact_storage_bytes must be a non-negative integer"
    with pytest.raises(ValueError, match=msg4):
        WeightMemoryEstimate(
            quantized_payload_bytes=100,
            unquantized_payload_bytes=0,
            scale_overhead_bytes=0,
            zero_point_overhead_bytes=0,
            metadata_bytes=0,
            alignment_overhead_bytes=0,
            total_bytes=100,
            effective_bits_per_weight=Fraction(16, 1),
            estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
            confidence=Confidence.EXACT,
            assumptions=(),
            warnings=(),
            artifact_storage_bytes=-1,
        )

    msg5 = "estimated_resident_weight_bytes must be a non-negative integer"
    with pytest.raises(ValueError, match=msg5):
        WeightMemoryEstimate(
            quantized_payload_bytes=100,
            unquantized_payload_bytes=0,
            scale_overhead_bytes=0,
            zero_point_overhead_bytes=0,
            metadata_bytes=0,
            alignment_overhead_bytes=0,
            total_bytes=100,
            effective_bits_per_weight=Fraction(16, 1),
            estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
            confidence=Confidence.EXACT,
            assumptions=(),
            warnings=(),
            estimated_resident_weight_bytes=-1,
        )

    msg6 = "estimated_resident_weight_bytes must equal total_bytes when set"
    with pytest.raises(ValueError, match=msg6):
        WeightMemoryEstimate(
            quantized_payload_bytes=100,
            unquantized_payload_bytes=0,
            scale_overhead_bytes=0,
            zero_point_overhead_bytes=0,
            metadata_bytes=0,
            alignment_overhead_bytes=0,
            total_bytes=100,
            effective_bits_per_weight=Fraction(16, 1),
            estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
            confidence=Confidence.EXACT,
            assumptions=(),
            warnings=(),
            estimated_resident_weight_bytes=200,
        )
