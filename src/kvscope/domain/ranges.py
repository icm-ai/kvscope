"""Range domain objects and interval arithmetic for bytes and ratios."""

from decimal import Decimal
from math import ceil
from typing import Annotated, Self

from pydantic import Field, StrictInt, model_validator

from kvscope.domain.base import DomainModel

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


def ceil_div(n: int, d: int) -> int:
    """Perform integer division rounded towards positive infinity.

    Requires non-negative inputs and positive divisor d > 0.
    """
    if isinstance(n, bool) or isinstance(d, bool):
        raise TypeError("n and d must be integers")
    if n < 0:
        raise ValueError("n must be non-negative")
    if d <= 0:
        raise ValueError("divisor d must be positive")
    return (n + d - 1) // d


def ceil_decimal_multiply(bytes_val: int, decimal_val: Decimal) -> int:
    """Multiply integer bytes by a Decimal ratio, rounded up to whole bytes."""
    if isinstance(bytes_val, bool) or not isinstance(bytes_val, int):
        raise TypeError("bytes_val must be an integer")
    if bytes_val < 0:
        raise ValueError("bytes_val must be non-negative")
    if not isinstance(decimal_val, Decimal):
        raise TypeError("decimal_val must be a Decimal")
    if decimal_val < 0:
        raise ValueError("decimal_val must be non-negative")

    result = Decimal(bytes_val) * decimal_val
    return int(ceil(result))


class ByteRange(DomainModel):
    """An interval representation of a memory size in bytes.

    Guarantees 0 <= lower_bytes <= expected_bytes <= upper_bytes.
    """

    lower_bytes: NonNegativeInt
    expected_bytes: NonNegativeInt
    upper_bytes: NonNegativeInt

    @model_validator(mode="after")
    def validate_range_ordering(self) -> Self:
        """Validate that lower <= expected <= upper."""
        if not (self.lower_bytes <= self.expected_bytes <= self.upper_bytes):
            msg = (
                f"Invalid ByteRange ordering: lower ({self.lower_bytes}) <= "
                f"expected ({self.expected_bytes}) <= upper ({self.upper_bytes})"
            )
            raise ValueError(msg)
        return self

    @classmethod
    def exact(cls, value_bytes: int) -> "ByteRange":
        """Construct an exact ByteRange where lower = expected = upper."""
        return cls(
            lower_bytes=value_bytes,
            expected_bytes=value_bytes,
            upper_bytes=value_bytes,
        )

    @property
    def is_exact(self) -> bool:
        """Return True if lower_bytes == expected_bytes == upper_bytes."""
        return self.lower_bytes == self.expected_bytes == self.upper_bytes


class RatioRange(DomainModel):
    """An interval representation of a dimensionless ratio (using Decimal).

    Guarantees 0 <= lower <= expected <= upper.
    """

    lower: Decimal
    expected: Decimal
    upper: Decimal

    @model_validator(mode="after")
    def validate_range_ordering(self) -> Self:
        """Validate that 0 <= lower <= expected <= upper."""
        if self.lower < 0:
            raise ValueError("Ratio lower bound must be non-negative")
        if not (self.lower <= self.expected <= self.upper):
            raise ValueError(
                f"Invalid RatioRange ordering: lower ({self.lower}) <= "
                f"expected ({self.expected}) <= upper ({self.upper}) violated"
            )
        return self

    @classmethod
    def exact(cls, value: Decimal | str | int) -> "RatioRange":
        """Construct an exact RatioRange."""
        dec = Decimal(str(value)) if not isinstance(value, Decimal) else value
        return cls(lower=dec, expected=dec, upper=dec)

    @property
    def is_exact(self) -> bool:
        """Return True if lower == expected == upper."""
        return self.lower == self.expected == self.upper


def add_byte_ranges(*ranges: ByteRange) -> ByteRange:
    """Sum a list of ByteRange objects component-wise.

    lower = sum(lower)
    expected = sum(expected)
    upper = sum(upper)
    """
    if not ranges:
        return ByteRange.exact(0)

    lower = sum(r.lower_bytes for r in ranges)
    expected = sum(r.expected_bytes for r in ranges)
    upper = sum(r.upper_bytes for r in ranges)

    return ByteRange(lower_bytes=lower, expected_bytes=expected, upper_bytes=upper)


def multiply_bytes_by_ratio_range(
    bytes_val: int | ByteRange, ratio: RatioRange
) -> ByteRange:
    """Multiply an integer byte amount or ByteRange by a RatioRange, rounding up.

    lower = ceil(bytes.lower * ratio.lower)
    expected = ceil(bytes.expected * ratio.expected)
    upper = ceil(bytes.upper * ratio.upper)
    """
    if isinstance(bytes_val, ByteRange):
        lower_base = bytes_val.lower_bytes
        expected_base = bytes_val.expected_bytes
        upper_base = bytes_val.upper_bytes
    elif isinstance(bytes_val, int) and not isinstance(bytes_val, bool):
        if bytes_val < 0:
            raise ValueError("bytes_val must be non-negative")
        lower_base = expected_base = upper_base = bytes_val
    else:
        raise TypeError("bytes_val must be an int or ByteRange")

    lower = ceil_decimal_multiply(lower_base, ratio.lower)
    expected = ceil_decimal_multiply(expected_base, ratio.expected)
    upper = ceil_decimal_multiply(upper_base, ratio.upper)

    return ByteRange(lower_bytes=lower, expected_bytes=expected, upper_bytes=upper)
