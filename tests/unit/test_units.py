"""Behavioral tests for exact memory unit conversion."""

from decimal import Decimal

import pytest

from kvscope.domain.units import (
    BYTES_PER_GIB,
    BYTES_PER_MIB,
    bytes_to_gib,
    bytes_to_mib,
    gib_to_bytes,
    mib_to_bytes,
)


def test_binary_units_convert_without_float_rounding() -> None:
    assert BYTES_PER_MIB == 1024**2
    assert BYTES_PER_GIB == 1024**3
    assert mib_to_bytes(2) == 2 * BYTES_PER_MIB
    assert gib_to_bytes(Decimal("1.5")) == 1_610_612_736
    assert bytes_to_mib(3 * BYTES_PER_MIB) == Decimal("3")
    assert bytes_to_gib(BYTES_PER_GIB + BYTES_PER_MIB) == Decimal("1.0009765625")


@pytest.mark.parametrize("converter", [mib_to_bytes, gib_to_bytes])
def test_unit_to_bytes_rejects_non_integral_byte_values(converter) -> None:
    with pytest.raises(ValueError, match="whole bytes"):
        converter(Decimal("0.0000000001"))


@pytest.mark.parametrize(
    "value",
    [-1, True, 1.0, "1"],
)
def test_unit_conversion_rejects_ambiguous_input_types(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        mib_to_bytes(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("converter", [bytes_to_mib, bytes_to_gib])
def test_bytes_to_unit_rejects_negative_bytes(converter) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        converter(-1)


@pytest.mark.parametrize("converter", [bytes_to_mib, bytes_to_gib])
@pytest.mark.parametrize("invalid_value", [1.5, True, "100"])
def test_bytes_to_unit_rejects_non_integer_types(
    converter, invalid_value: object
) -> None:
    with pytest.raises(TypeError, match="bytes must be an integer"):
        converter(invalid_value)  # type: ignore[arg-type]
