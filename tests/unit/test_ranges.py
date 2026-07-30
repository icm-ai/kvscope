"""Unit tests for ByteRange, RatioRange, and interval arithmetic helpers."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from kvscope.domain.ranges import (
    ByteRange,
    RatioRange,
    add_byte_ranges,
    ceil_decimal_multiply,
    ceil_div,
    multiply_bytes_by_ratio_range,
)


def test_byte_range_valid_exact() -> None:
    br = ByteRange.exact(1024)
    assert br.lower_bytes == 1024
    assert br.expected_bytes == 1024
    assert br.upper_bytes == 1024
    assert br.is_exact is True


def test_byte_range_valid_interval() -> None:
    br = ByteRange(lower_bytes=100, expected_bytes=200, upper_bytes=300)
    assert br.lower_bytes == 100
    assert br.expected_bytes == 200
    assert br.upper_bytes == 300
    assert br.is_exact is False


def test_byte_range_invalid_ordering() -> None:
    with pytest.raises(ValidationError):
        ByteRange(lower_bytes=300, expected_bytes=200, upper_bytes=300)

    with pytest.raises(ValidationError):
        ByteRange(lower_bytes=100, expected_bytes=400, upper_bytes=300)


def test_ratio_range_valid() -> None:
    rr = RatioRange(
        lower=Decimal("0.05"), expected=Decimal("0.10"), upper=Decimal("0.15")
    )
    assert rr.lower == Decimal("0.05")
    assert rr.expected == Decimal("0.10")
    assert rr.upper == Decimal("0.15")
    assert rr.is_exact is False


def test_ratio_range_exact() -> None:
    rr = RatioRange.exact(Decimal("0.05"))
    assert rr.is_exact is True


def test_ratio_range_invalid_ordering() -> None:
    with pytest.raises(ValidationError):
        RatioRange(
            lower=Decimal("0.20"), expected=Decimal("0.10"), upper=Decimal("0.15")
        )


def test_ceil_div() -> None:
    assert ceil_div(0, 5) == 0
    assert ceil_div(5, 5) == 1
    assert ceil_div(6, 5) == 2
    assert ceil_div(9, 5) == 2
    assert ceil_div(10, 5) == 2
    with pytest.raises(ValueError):
        ceil_div(-1, 5)
    with pytest.raises(ValueError):
        ceil_div(5, 0)


def test_ceil_decimal_multiply() -> None:
    assert ceil_decimal_multiply(100, Decimal("0.05")) == 5
    assert ceil_decimal_multiply(101, Decimal("0.05")) == 6  # 5.05 -> ceil 6
    assert ceil_decimal_multiply(0, Decimal("0.5")) == 0


def test_add_byte_ranges() -> None:
    r1 = ByteRange(lower_bytes=10, expected_bytes=20, upper_bytes=30)
    r2 = ByteRange(lower_bytes=5, expected_bytes=15, upper_bytes=25)
    sum_r = add_byte_ranges(r1, r2)
    assert sum_r.lower_bytes == 15
    assert sum_r.expected_bytes == 35
    assert sum_r.upper_bytes == 55


def test_multiply_bytes_by_ratio_range() -> None:
    ratio = RatioRange(
        lower=Decimal("0.10"), expected=Decimal("0.20"), upper=Decimal("0.30")
    )
    # Integer bytes multiplication
    res = multiply_bytes_by_ratio_range(1000, ratio)
    assert res.lower_bytes == 100
    assert res.expected_bytes == 200
    assert res.upper_bytes == 300

    # ByteRange multiplication
    bytes_range = ByteRange(lower_bytes=500, expected_bytes=1000, upper_bytes=2000)
    res_range = multiply_bytes_by_ratio_range(bytes_range, ratio)
    assert res_range.lower_bytes == 50  # ceil(500 * 0.10)
    assert res_range.expected_bytes == 200  # ceil(1000 * 0.20)
    assert res_range.upper_bytes == 600  # ceil(2000 * 0.30)


def test_ranges_edge_cases() -> None:
    # Empty add_byte_ranges
    assert add_byte_ranges().expected_bytes == 0

    # TypeError on ceil_div with bool
    with pytest.raises(TypeError):
        ceil_div(True, 5)
    with pytest.raises(TypeError):
        ceil_div(10, False)

    # TypeError and ValueError on ceil_decimal_multiply
    with pytest.raises(TypeError):
        ceil_decimal_multiply("invalid", Decimal("0.5"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ceil_decimal_multiply(-10, Decimal("0.5"))
    with pytest.raises(TypeError):
        ceil_decimal_multiply(10, 0.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ceil_decimal_multiply(10, Decimal("-0.5"))

    # Negative lower bound for RatioRange
    with pytest.raises(ValidationError):
        RatioRange(lower=Decimal("-0.1"), expected=Decimal("0.1"), upper=Decimal("0.2"))

    # Invalid types and negative inputs for multiply_bytes_by_ratio_range
    ratio = RatioRange.exact(Decimal("0.1"))
    with pytest.raises(ValueError):
        multiply_bytes_by_ratio_range(-5, ratio)
    with pytest.raises(TypeError):
        multiply_bytes_by_ratio_range("invalid", ratio)  # type: ignore[arg-type]
