"""Unit tests for SignedByteRange and range subtraction arithmetic."""

import pytest
from pydantic import ValidationError

from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import (
    SignedByteRange,
    subtract_byte_ranges,
    subtract_exact_bytes_from_range,
    subtract_range_from_exact_bytes,
)


def test_signed_byte_range_validation():
    sbr = SignedByteRange(lower_bytes=-100, expected_bytes=0, upper_bytes=100)
    assert sbr.lower_bytes == -100
    assert sbr.expected_bytes == 0
    assert sbr.upper_bytes == 100
    assert not sbr.is_exact

    exact_sbr = SignedByteRange.exact(-50)
    assert exact_sbr.is_exact
    assert exact_sbr.lower_bytes == -50

    with pytest.raises(ValidationError):
        SignedByteRange(lower_bytes=10, expected_bytes=0, upper_bytes=100)


def test_subtract_byte_ranges():
    budget = ByteRange(lower_bytes=1000, expected_bytes=2000, upper_bytes=3000)
    req = ByteRange(lower_bytes=500, expected_bytes=1500, upper_bytes=2500)

    result = subtract_byte_ranges(budget, req)

    # lower = budget.lower - req.upper = 1000 - 2500 = -1500
    # expected = budget.expected - req.expected = 2000 - 1500 = 500
    # upper = budget.upper - req.lower = 3000 - 500 = 2500
    assert result.lower_bytes == -1500
    assert result.expected_bytes == 500
    assert result.upper_bytes == 2500


def test_subtract_exact_bytes_from_range():
    budget_bytes = 10000
    req = ByteRange(lower_bytes=2000, expected_bytes=5000, upper_bytes=8000)

    result = subtract_exact_bytes_from_range(budget_bytes, req)

    assert result.lower_bytes == 2000  # 10000 - 8000
    assert result.expected_bytes == 5000  # 10000 - 5000
    assert result.upper_bytes == 8000  # 10000 - 2000


def test_subtract_range_from_exact_bytes():
    budget = ByteRange(lower_bytes=1000, expected_bytes=2000, upper_bytes=3000)
    req_bytes = 1500

    result = subtract_range_from_exact_bytes(budget, req_bytes)

    assert result.lower_bytes == -500  # 1000 - 1500
    assert result.expected_bytes == 500  # 2000 - 1500
    assert result.upper_bytes == 1500  # 3000 - 1500


def test_signed_byte_range_json_roundtrip():
    sbr = SignedByteRange(lower_bytes=-2000, expected_bytes=0, upper_bytes=5000)
    json_str = sbr.model_dump_json()
    loaded = SignedByteRange.model_validate_json(json_str)
    assert loaded == sbr
