"""Supported weight and KV cache data types."""

from enum import StrEnum


class WeightDType(StrEnum):
    """Weight precision and its effective bits per weight."""

    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    FP8 = "fp8"
    INT8 = "int8"
    INT4 = "int4"

    @property
    def bits_per_weight(self) -> int:
        """Return the nominal number of bits represented by one weight."""
        return {
            WeightDType.FP32: 32,
            WeightDType.FP16: 16,
            WeightDType.BF16: 16,
            WeightDType.FP8: 8,
            WeightDType.INT8: 8,
            WeightDType.INT4: 4,
        }[self]


class KVDType(StrEnum):
    """KV cache element precision and its bytes per element."""

    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    FP8 = "fp8"
    INT8 = "int8"

    @property
    def bytes_per_element(self) -> int:
        """Return the integral storage bytes for one KV cache element."""
        return (
            4
            if self is KVDType.FP32
            else 2
            if self in {KVDType.FP16, KVDType.BF16}
            else 1
        )
