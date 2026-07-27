"""Behavioral tests for the core model domain objects."""

import re

import pytest
from pydantic import ValidationError

from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.model import ModelSpec


def valid_model_data() -> dict[str, object]:
    """Return the smallest valid model configuration used by these tests."""
    return {
        "model_id": "example/model",
        "architecture": "example",
        "num_hidden_layers": 24,
        "hidden_size": 4096,
        "num_attention_heads": 32,
        "num_key_value_heads": 8,
        "head_dim": 128,
        "source": "manual",
    }


def test_model_spec_validates_architecture_invariants() -> None:
    model = ModelSpec.model_validate(valid_model_data())

    assert model.num_attention_heads // model.num_key_value_heads == 4
    assert model.hidden_size == model.num_attention_heads * model.head_dim
    assert model.model_config["frozen"] is True


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "num_key_value_heads",
            3,
            "num_attention_heads must be divisible by num_key_value_heads",
        ),
        (
            "hidden_size",
            4000,
            "hidden_size must equal num_attention_heads * head_dim",
        ),
    ],
)
def test_model_spec_rejects_inconsistent_attention_dimensions(
    field: str, value: int, message: str
) -> None:
    data = valid_model_data()
    data[field] = value

    with pytest.raises(ValidationError, match=re.escape(message)):
        ModelSpec.model_validate(data)


def test_dtype_enums_expose_storage_precision() -> None:
    assert WeightDType.INT4.bits_per_weight == 4
    assert WeightDType.FP16.bits_per_weight == 16
    assert KVDType.FP16.bytes_per_element == 2
    assert KVDType.INT8.bytes_per_element == 1
