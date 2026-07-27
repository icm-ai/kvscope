"""Exact binary memory unit conversion helpers."""

from decimal import Decimal
from numbers import Integral
from typing import TypeAlias

BYTES_PER_MIB = 1024**2
BYTES_PER_GIB = 1024**3

UnitValue: TypeAlias = int | Decimal

__all__ = [
    "BYTES_PER_GIB",
    "BYTES_PER_MIB",
    "bytes_to_gib",
    "bytes_to_mib",
    "gib_to_bytes",
    "mib_to_bytes",
]


def _as_non_negative_decimal(value: UnitValue) -> Decimal:
    """Convert supported exact numeric input to a non-negative Decimal."""
    if isinstance(value, bool) or not isinstance(value, (Integral, Decimal)):
        raise TypeError("unit values must be integers or Decimal instances")
    decimal_value = Decimal(value)
    if decimal_value < 0:
        raise ValueError("unit values must be non-negative")
    return decimal_value


def _unit_to_bytes(value: UnitValue, multiplier: int) -> int:
    """Convert a binary unit value and require a whole number of bytes."""
    byte_value = _as_non_negative_decimal(value) * multiplier
    if byte_value != byte_value.to_integral_value():
        raise ValueError("unit value must convert to whole bytes")
    return int(byte_value)


def mib_to_bytes(value: UnitValue) -> int:
    """Convert an exact MiB value to integer bytes."""
    return _unit_to_bytes(value, BYTES_PER_MIB)


def gib_to_bytes(value: UnitValue) -> int:
    """Convert an exact GiB value to integer bytes."""
    return _unit_to_bytes(value, BYTES_PER_GIB)


def bytes_to_mib(value: int) -> Decimal:
    """Convert non-negative integer bytes to an exact MiB Decimal."""
    _validate_bytes(value)
    return Decimal(value) / BYTES_PER_MIB


def bytes_to_gib(value: int) -> Decimal:
    """Convert non-negative integer bytes to an exact GiB Decimal."""
    _validate_bytes(value)
    return Decimal(value) / BYTES_PER_GIB


def _validate_bytes(value: int) -> None:
    """Validate the integer-byte side of a conversion."""
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("bytes must be an integer")
    if value < 0:
        raise ValueError("bytes must be non-negative")
