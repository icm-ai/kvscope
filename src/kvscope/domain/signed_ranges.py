"""Signed byte range domain object and range subtraction arithmetic."""

from typing import Self

from pydantic import StrictInt, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.ranges import ByteRange


class SignedByteRange(DomainModel):
    """An interval representation of a memory difference in integer bytes.

    Guarantees lower_bytes <= expected_bytes <= upper_bytes.
    Negative values represent memory deficits; positive values represent headroom.
    """

    lower_bytes: StrictInt
    expected_bytes: StrictInt
    upper_bytes: StrictInt

    @model_validator(mode="after")
    def validate_range_ordering(self) -> Self:
        """Validate that lower <= expected <= upper."""
        if not (self.lower_bytes <= self.expected_bytes <= self.upper_bytes):
            msg = (
                f"Invalid SignedByteRange ordering: lower ({self.lower_bytes}) <= "
                f"expected ({self.expected_bytes}) <= upper ({self.upper_bytes})"
            )
            raise ValueError(msg)
        return self

    @classmethod
    def exact(cls, value_bytes: int) -> "SignedByteRange":
        """Construct an exact SignedByteRange where lower = expected = upper."""
        return cls(
            lower_bytes=value_bytes,
            expected_bytes=value_bytes,
            upper_bytes=value_bytes,
        )

    @property
    def is_exact(self) -> bool:
        """Return True if lower_bytes == expected_bytes == upper_bytes."""
        return self.lower_bytes == self.expected_bytes == self.upper_bytes


def subtract_byte_ranges(
    budget: ByteRange,
    requirement: ByteRange,
) -> SignedByteRange:
    """Subtract a requirement ByteRange from a budget ByteRange.

    result.lower = budget.lower - requirement.upper
    result.expected = budget.expected - requirement.expected
    result.upper = budget.upper - requirement.lower
    """
    lower = budget.lower_bytes - requirement.upper_bytes
    expected = budget.expected_bytes - requirement.expected_bytes
    upper = budget.upper_bytes - requirement.lower_bytes

    return SignedByteRange(
        lower_bytes=lower,
        expected_bytes=expected,
        upper_bytes=upper,
    )


def subtract_exact_bytes_from_range(
    budget_bytes: int,
    requirement: ByteRange,
) -> SignedByteRange:
    """Subtract a requirement ByteRange from an exact integer budget amount.

    result.lower = budget_bytes - requirement.upper
    result.expected = budget_bytes - requirement.expected
    result.upper = budget_bytes - requirement.lower
    """
    lower = budget_bytes - requirement.upper_bytes
    expected = budget_bytes - requirement.expected_bytes
    upper = budget_bytes - requirement.lower_bytes

    return SignedByteRange(
        lower_bytes=lower,
        expected_bytes=expected,
        upper_bytes=upper,
    )


def subtract_range_from_exact_bytes(
    budget: ByteRange,
    requirement_bytes: int,
) -> SignedByteRange:
    """Subtract an exact integer requirement amount from a budget ByteRange.

    result.lower = budget.lower - requirement_bytes
    result.expected = budget.expected - requirement_bytes
    result.upper = budget.upper - requirement_bytes
    """
    lower = budget.lower_bytes - requirement_bytes
    expected = budget.expected_bytes - requirement_bytes
    upper = budget.upper_bytes - requirement_bytes

    return SignedByteRange(
        lower_bytes=lower,
        expected_bytes=expected,
        upper_bytes=upper,
    )
