"""Phase 5 model resolver behavior."""

import json
from pathlib import Path

import pytest

from kvscope import resolve_model
from kvscope.domain import ModelSpec
from kvscope.errors import ModelConfigConflictError, ModelSourceNotFoundError
from kvscope.resolvers.local_config import MAX_CONFIG_BYTES

CONFIG = {
    "model_id": "local-qwen",
    "model_type": "qwen2",
    "num_hidden_layers": 4,
    "hidden_size": 512,
    "num_attention_heads": 8,
    "num_key_value_heads": 2,
    "vocab_size": 1000,
}


def test_explicit_mapping_is_normalized_without_mutation() -> None:
    source = dict(CONFIG)
    resolved = resolve_model(source)
    assert source == CONFIG
    assert resolved.adapter_id == "qwen"
    assert resolved.spec.head_dim == 64
    assert resolved.source.source_type == "explicit"


def test_model_spec_is_returned_directly() -> None:
    spec = ModelSpec(
        model_id="already-normalized",
        architecture="custom",
        num_hidden_layers=2,
        hidden_size=128,
        num_attention_heads=4,
        num_key_value_heads=4,
        head_dim=32,
        source="test",
    )
    assert resolve_model(spec).spec == spec


def test_local_file_and_directory(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps(CONFIG), encoding="utf-8")
    assert resolve_model(config).source.source_type == "local"
    assert resolve_model(tmp_path).spec.model_id == "local-qwen"


def test_local_missing_path_does_not_become_network_source(tmp_path: Path) -> None:
    with pytest.raises(ModelSourceNotFoundError) as error:
        resolve_model(tmp_path / "missing-model")
    assert error.value.code == "local_source_not_found"


def test_alias_conflict_is_rejected() -> None:
    source = dict(CONFIG)
    source["n_layer"] = 5
    with pytest.raises(ModelConfigConflictError):
        resolve_model(source)


def test_builtin_registry_alias() -> None:
    resolved = resolve_model("Qwen/example")
    assert resolved.source.source_type == "registry"
    assert resolved.spec.num_key_value_heads == 8


def test_local_size_limit_is_public_constant() -> None:
    assert MAX_CONFIG_BYTES == 10 * 1024 * 1024
