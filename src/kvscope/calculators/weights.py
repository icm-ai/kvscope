"""Pure model-weight sizing formulas and the Weight Engine entry point."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from math import isfinite
from typing import TypeAlias

from kvscope.domain.dtypes import WeightDType
from kvscope.domain.enums import Confidence
from kvscope.domain.estimate import EstimateComponent
from kvscope.domain.weight import WeightArtifactSummary
from kvscope.errors import InvalidModelConfigError

BitsValue: TypeAlias = int | str | Decimal | Fraction | float


class WeightEstimationMethod(StrEnum):
    """Input source used by a weight estimate."""

    PARAMETER_COUNT = "parameter_count"
    GROUP_QUANTIZATION = "group_quantization"
    ARTIFACT_SUMMARY = "artifact_summary"


@dataclass(frozen=True, slots=True)
class WeightMemoryEstimate:
    """Explainable weight-memory result with integer byte components."""

    quantized_payload_bytes: int
    unquantized_payload_bytes: int
    scale_overhead_bytes: int
    zero_point_overhead_bytes: int
    metadata_bytes: int
    alignment_overhead_bytes: int
    total_bytes: int
    effective_bits_per_weight: Fraction | None
    estimation_method: WeightEstimationMethod
    confidence: Confidence
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    artifact_storage_bytes: int | None = None
    estimated_resident_weight_bytes: int | None = None

    def __post_init__(self) -> None:
        """Validate invariants even when a result is constructed directly."""
        byte_fields = (
            "quantized_payload_bytes",
            "unquantized_payload_bytes",
            "scale_overhead_bytes",
            "zero_point_overhead_bytes",
            "metadata_bytes",
            "alignment_overhead_bytes",
            "total_bytes",
        )
        for field_name in byte_fields:
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        components_total = sum(getattr(self, name) for name in byte_fields[:-1])
        if self.total_bytes != components_total:
            raise ValueError("total_bytes must equal all byte components combined")
        if self.effective_bits_per_weight is not None and (
            not isinstance(self.effective_bits_per_weight, Fraction)
            or self.effective_bits_per_weight <= 0
        ):
            raise ValueError("effective_bits_per_weight must be positive or None")
        if self.artifact_storage_bytes is not None and (
            type(self.artifact_storage_bytes) is not int
            or self.artifact_storage_bytes < 0
        ):
            raise ValueError("artifact_storage_bytes must be a non-negative integer")
        if self.estimated_resident_weight_bytes is not None and (
            type(self.estimated_resident_weight_bytes) is not int
            or self.estimated_resident_weight_bytes < 0
        ):
            raise ValueError(
                "estimated_resident_weight_bytes must be a non-negative integer"
            )
        if (
            self.estimated_resident_weight_bytes is not None
            and self.estimated_resident_weight_bytes != self.total_bytes
        ):
            raise ValueError(
                "estimated_resident_weight_bytes must equal total_bytes when set"
            )

    def to_estimate_component(self) -> EstimateComponent:
        """Convert the result to the existing report component schema."""
        return EstimateComponent(
            name="weights",
            bytes=self.total_bytes,
            confidence=self.confidence,
            formula=(
                "quantized_payload + unquantized_payload + scale + "
                "zero_point + metadata + alignment"
            ),
        )


def _invalid(field_name: str, reason: str) -> InvalidModelConfigError:
    """Create a consistently locatable Weight Engine input error."""
    return InvalidModelConfigError(f"{field_name}: {reason}")


def _positive_int(value: object, field_name: str) -> int:
    """Validate a strict positive integer input."""
    if type(value) is not int or value <= 0:
        raise _invalid(field_name, "must be a positive integer")
    return value


def _nonnegative_int(value: object, field_name: str) -> int:
    """Validate a strict non-negative integer input."""
    if type(value) is not int or value < 0:
        raise _invalid(field_name, "must be a non-negative integer")
    return value


def _fraction(value: BitsValue, field_name: str) -> Fraction:
    """Convert a user precision value without multiplying large floats."""
    try:
        if isinstance(value, float):
            if not isfinite(value):
                raise ValueError
            return Fraction(str(value))
        return Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise _invalid(field_name, "must be a finite numeric value") from exc


def _positive_fraction(value: BitsValue, field_name: str) -> Fraction:
    """Validate a positive exact rational input."""
    result = _fraction(value, field_name)
    if result <= 0:
        raise _invalid(field_name, "must be greater than zero")
    return result


def _ceil_fraction(value: Fraction) -> int:
    """Return the mathematical ceiling of an exact rational value."""
    return (value.numerator + value.denominator - 1) // value.denominator


def _resolve_bits(
    *,
    dtype: WeightDType | None,
    custom_bits: BitsValue | None,
    field_name: str,
) -> Fraction:
    """Resolve dtype and custom bits, rejecting contradictory precision inputs."""
    if dtype is not None and not isinstance(dtype, WeightDType):
        raise _invalid("dtype", "must be a WeightDType")
    dtype_bits = Fraction(dtype.bits_per_weight) if dtype is not None else None
    custom = (
        _positive_fraction(custom_bits, field_name)
        if custom_bits is not None
        else None
    )
    if dtype_bits is not None and custom is not None and dtype_bits != custom:
        raise _invalid(field_name, "conflicts with dtype.bits_per_weight")
    if dtype_bits is None and custom is None:
        raise _invalid(field_name, "must be supplied with dtype or custom bits")
    if dtype_bits is not None:
        return dtype_bits
    if custom is not None:
        return custom
    raise AssertionError("at least one bit source must have been supplied")


def _alignment_overhead(
    base_bytes: int,
    *,
    alignment: int | None,
    explicit_alignment_bytes: int,
) -> int:
    """Apply an optional alignment boundary exactly once."""
    if alignment is None:
        return explicit_alignment_bytes
    _positive_int(alignment, "alignment")
    aligned_bytes = ((base_bytes + alignment - 1) // alignment) * alignment
    return explicit_alignment_bytes + aligned_bytes - base_bytes


def _effective_bits(total_bytes: int, parameter_count: int) -> Fraction:
    """Return total resident bits per model parameter exactly."""
    return Fraction(total_bytes * 8, parameter_count)


def _estimate_artifact(artifact: WeightArtifactSummary) -> WeightMemoryEstimate:
    """Estimate resident bytes from an upstream artifact summary."""
    return WeightMemoryEstimate(
        quantized_payload_bytes=artifact.payload_bytes,
        unquantized_payload_bytes=0,
        scale_overhead_bytes=0,
        zero_point_overhead_bytes=0,
        metadata_bytes=artifact.metadata_bytes,
        alignment_overhead_bytes=artifact.alignment_bytes,
        total_bytes=artifact.storage_bytes,
        effective_bits_per_weight=None,
        estimation_method=WeightEstimationMethod.ARTIFACT_SUMMARY,
        confidence=Confidence.HIGH,
        assumptions=(
            "artifact byte counts were supplied by an upstream parser",
            "resident weight bytes are estimated from artifact storage bytes",
        ),
        warnings=(
            "artifact storage bytes are not a measurement of device-resident memory",
            "mmap, loader buffers, runtime overhead, and allocator behavior "
            "are excluded",
        ),
        artifact_storage_bytes=artifact.storage_bytes,
        estimated_resident_weight_bytes=artifact.storage_bytes,
    )


def estimate_weight_memory(
    parameter_count: int | None = None,
    *,
    dtype: WeightDType | None = None,
    bits_per_weight: BitsValue | None = None,
    quantized_parameter_count: int | None = None,
    quantization_bits: BitsValue | None = None,
    group_size: int | None = None,
    scale_bytes_per_group: int = 0,
    zero_point_bytes_per_group: int = 0,
    unquantized_parameter_count: int | None = None,
    unquantized_fraction: BitsValue | None = None,
    unquantized_dtype: WeightDType | None = None,
    metadata_bytes: int = 0,
    alignment: int | None = None,
    alignment_bytes: int | None = None,
    artifact: WeightArtifactSummary | None = None,
) -> WeightMemoryEstimate:
    """Estimate model-weight bytes using parameter, group, or artifact inputs.

    No resolver or filesystem behavior is performed. Formula modes use exact
    rational arithmetic and round sub-byte payloads and group counts upward.
    """
    if artifact is not None:
        if not isinstance(artifact, WeightArtifactSummary):
            raise _invalid("artifact", "must be a WeightArtifactSummary")
        formula_inputs = (
            parameter_count,
            dtype,
            bits_per_weight,
            quantized_parameter_count,
            quantization_bits,
            group_size,
            unquantized_parameter_count,
            unquantized_fraction,
            unquantized_dtype,
            alignment,
        )
        if any(value is not None for value in formula_inputs) or any(
            value != 0
            for value in (
                scale_bytes_per_group,
                zero_point_bytes_per_group,
                metadata_bytes,
            )
        ) or alignment_bytes not in (None, 0):
            raise _invalid(
                "artifact",
                "cannot be combined with parameter-count or quantization inputs",
            )
        return _estimate_artifact(artifact)

    total_parameters = _positive_int(parameter_count, "parameter_count")
    scale_bytes = _nonnegative_int(scale_bytes_per_group, "scale_bytes_per_group")
    zero_point_bytes = _nonnegative_int(
        zero_point_bytes_per_group, "zero_point_bytes_per_group"
    )
    metadata = _nonnegative_int(metadata_bytes, "metadata_bytes")
    explicit_alignment = (
        0
        if alignment_bytes is None
        else _nonnegative_int(alignment_bytes, "alignment_bytes")
    )
    if alignment is not None:
        _positive_int(alignment, "alignment")
    if unquantized_dtype is not None and not isinstance(
        unquantized_dtype, WeightDType
    ):
        raise _invalid("unquantized_dtype", "must be a WeightDType")

    group_mode = any(
        value is not None
        for value in (
            quantized_parameter_count,
            quantization_bits,
            group_size,
            unquantized_parameter_count,
            unquantized_fraction,
        )
    ) or scale_bytes != 0 or zero_point_bytes != 0 or unquantized_dtype is not None

    if not group_mode:
        bits = _resolve_bits(
            dtype=dtype,
            custom_bits=bits_per_weight,
            field_name="bits_per_weight",
        )
        payload = _ceil_fraction(Fraction(total_parameters) * bits / 8)
        base_bytes = payload + metadata + explicit_alignment
        alignment_overhead = _alignment_overhead(
            base_bytes,
            alignment=alignment,
            explicit_alignment_bytes=0,
        )
        total = base_bytes + alignment_overhead
        return WeightMemoryEstimate(
            quantized_payload_bytes=payload,
            unquantized_payload_bytes=0,
            scale_overhead_bytes=0,
            zero_point_overhead_bytes=0,
            metadata_bytes=metadata,
            alignment_overhead_bytes=explicit_alignment + alignment_overhead,
            total_bytes=total,
            effective_bits_per_weight=_effective_bits(total, total_parameters),
            estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
            confidence=Confidence.EXACT,
            assumptions=(
                "parameter_count represents all model parameters",
                "payload is rounded up to a whole byte",
            ),
            warnings=(
                "theoretical payload excludes runtime overhead and loader behavior",
            ),
            estimated_resident_weight_bytes=total,
        )

    if dtype is not None and not isinstance(dtype, WeightDType):
        raise _invalid("dtype", "must be a WeightDType")
    if bits_per_weight is not None and quantization_bits is not None:
        if _positive_fraction(bits_per_weight, "bits_per_weight") != _positive_fraction(
            quantization_bits, "quantization_bits"
        ):
            raise _invalid("quantization_bits", "conflicts with bits_per_weight")
    quant_bits = _resolve_bits(
        dtype=dtype,
        custom_bits=quantization_bits
        if quantization_bits is not None
        else bits_per_weight,
        field_name="quantization_bits",
    )
    if group_size is None:
        raise _invalid("group_size", "must be supplied in group quantization mode")
    groupsize = _positive_int(group_size, "group_size")

    if quantized_parameter_count is None:
        quantized_count: int | None = None
    else:
        quantized_count = _nonnegative_int(
            quantized_parameter_count, "quantized_parameter_count"
        )

    fraction_count: int | None = None
    if unquantized_fraction is not None:
        fraction_value = _fraction(unquantized_fraction, "unquantized_fraction")
        if fraction_value < 0 or fraction_value > 1:
            raise _invalid("unquantized_fraction", "must be between 0 and 1")
        fraction_count = _ceil_fraction(Fraction(total_parameters) * fraction_value)

    if unquantized_parameter_count is not None:
        unquantized_count = _nonnegative_int(
            unquantized_parameter_count, "unquantized_parameter_count"
        )
        if fraction_count is not None and unquantized_count != fraction_count:
            raise _invalid(
                "unquantized_parameter_count",
                "conflicts with unquantized_fraction",
            )
        explicit_unquantized = True
    elif fraction_count is not None:
        unquantized_count = fraction_count
        explicit_unquantized = True
    else:
        unquantized_count = None
        explicit_unquantized = False

    if quantized_count is None:
        quantized_count = (
            total_parameters - unquantized_count
            if unquantized_count is not None
            else total_parameters
        )
    if unquantized_count is None:
        unquantized_count = total_parameters - quantized_count
    if quantized_count > total_parameters:
        raise _invalid("quantized_parameter_count", "must not exceed parameter_count")
    if quantized_count + unquantized_count > total_parameters:
        raise _invalid(
            "unquantized_parameter_count",
            "quantized and unquantized counts exceed parameter_count",
        )
    if quantized_parameter_count is not None and explicit_unquantized and (
        quantized_count + unquantized_count != total_parameters
    ):
        raise _invalid(
            "quantized_parameter_count",
            "quantized and unquantized counts must cover parameter_count",
        )

    if unquantized_count > 0 and unquantized_dtype is None:
        raise _invalid(
            "unquantized_dtype",
            "must be supplied when unquantized parameters are present",
        )
    quantized_payload = _ceil_fraction(Fraction(quantized_count) * quant_bits / 8)
    number_of_groups = (quantized_count + groupsize - 1) // groupsize
    scale_overhead = number_of_groups * scale_bytes
    zero_point_overhead = number_of_groups * zero_point_bytes
    unquantized_bits = (
        Fraction(unquantized_dtype.bits_per_weight)
        if unquantized_dtype is not None
        else Fraction(0)
    )
    unquantized_payload = _ceil_fraction(
        Fraction(unquantized_count) * unquantized_bits / 8
    )
    base_bytes = (
        quantized_payload
        + unquantized_payload
        + scale_overhead
        + zero_point_overhead
        + metadata
        + explicit_alignment
    )
    computed_alignment = _alignment_overhead(
        base_bytes,
        alignment=alignment,
        explicit_alignment_bytes=0,
    )
    total = base_bytes + computed_alignment
    return WeightMemoryEstimate(
        quantized_payload_bytes=quantized_payload,
        unquantized_payload_bytes=unquantized_payload,
        scale_overhead_bytes=scale_overhead,
        zero_point_overhead_bytes=zero_point_overhead,
        metadata_bytes=metadata,
        alignment_overhead_bytes=explicit_alignment + computed_alignment,
        total_bytes=total,
        effective_bits_per_weight=_effective_bits(total, total_parameters),
        estimation_method=WeightEstimationMethod.GROUP_QUANTIZATION,
        confidence=Confidence.EXACT,
        assumptions=(
            "group count is ceil(quantized_parameter_count / group_size)",
            "quantized and unquantized payloads are rounded up to whole bytes",
        ),
        warnings=(
            "INT4 is a theoretical payload; group metadata and unquantized "
            "parameters are included",
            "runtime overhead, mmap behavior, and allocator effects are excluded",
        ),
        estimated_resident_weight_bytes=total,
    )
