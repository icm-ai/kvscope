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
    assert model.model_config["frozen"] is True


def test_model_spec_supports_non_standard_head_dimensions() -> None:
    """Gemma 7B has hidden_size=3072, 16 attention heads, and head_dim=256."""
    gemma_data = {
        "model_id": "google/gemma-7b",
        "architecture": "gemma",
        "num_hidden_layers": 28,
        "hidden_size": 3072,
        "num_attention_heads": 16,
        "num_key_value_heads": 16,
        "head_dim": 256,
        "source": "manual",
    }
    model = ModelSpec.model_validate(gemma_data)
    assert model.head_dim == 256
    assert model.hidden_size == 3072


def test_model_spec_rejects_inconsistent_attention_dimensions() -> None:
    data = valid_model_data()
    data["num_key_value_heads"] = 3

    msg = "num_attention_heads must be divisible by num_key_value_heads"
    with pytest.raises(ValidationError, match=re.escape(msg)):
        ModelSpec.model_validate(data)


def test_dtype_enums_expose_storage_precision() -> None:
    assert WeightDType.INT4.bits_per_weight == 4
    assert WeightDType.FP16.bits_per_weight == 16
    assert KVDType.FP16.bytes_per_element == 2
    assert KVDType.INT8.bytes_per_element == 1

