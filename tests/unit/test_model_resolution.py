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


def test_offline_mode_zero_network(tmp_path: Path) -> None:
    from unittest.mock import MagicMock, patch

    from kvscope.errors import OfflineCacheMissError

    mock_download = MagicMock()
    mock_api = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "huggingface_hub": MagicMock(
                hf_hub_download=mock_download, HfApi=mock_api
            )
        },
    ):
        with pytest.raises(OfflineCacheMissError):
            resolve_model(
                "org/custom-model-id",
                offline=True,
                cache_dir=tmp_path,
            )
    mock_download.assert_not_called()
    mock_api.assert_not_called()


def test_unknown_architecture_strict_failure() -> None:
    from kvscope.errors import UnsupportedArchitectureError

    source = {
        "model_id": "test-unknown",
        "model_type": "unknown_future_arch",
        "num_hidden_layers": 4,
        "hidden_size": 512,
        "num_attention_heads": 8,
        "num_key_value_heads": 8,
    }
    with pytest.raises(UnsupportedArchitectureError) as error:
        resolve_model(source, allow_generic=False)
    assert error.value.code == "unsupported_architecture"


def test_unknown_architecture_generic_fallback() -> None:
    from kvscope.domain.enums import Confidence

    source = {
        "model_id": "test-generic",
        "model_type": "unknown_future_arch",
        "num_hidden_layers": 4,
        "hidden_size": 512,
        "num_attention_heads": 8,
        "num_key_value_heads": 8,
    }
    resolved = resolve_model(source, allow_generic=True)
    assert resolved.adapter_id == "generic_decoder"
    assert resolved.confidence == Confidence.MEDIUM
    assert any("Generic adapter was used" in w for w in resolved.warnings)


def test_multimodal_model_warning() -> None:
    source = {
        "model_id": "test-multimodal",
        "model_type": "llava_next",
        "vision_config": {"hidden_size": 1024},
        "num_hidden_layers": 4,
        "hidden_size": 512,
        "num_attention_heads": 8,
        "num_key_value_heads": 8,
    }
    resolved = resolve_model(source)
    assert any(
        "vision encoder is not included" in w
        and "multimodal memory is not fully estimated" in w
        for w in resolved.warnings
    )



def test_full_provenance_recording() -> None:
    source = dict(CONFIG)
    resolved = resolve_model(source, revision="v1.0")
    assert resolved.source.source_type == "explicit"
    assert resolved.source.requested_revision == "v1.0"
    assert resolved.source.resolver_id == "explicit_config"
    assert resolved.source.adapter_id == "qwen"
    assert len(resolved.source.config_digest) == 64
    assert resolved.source.confidence.value in ("high", "medium")
    assert isinstance(resolved.source.attempts, list)
    assert len(resolved.source.attempts) > 0


