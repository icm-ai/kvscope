"""Built-in decoder architecture adapters."""

from collections.abc import Mapping
from typing import Any

from kvscope.adapters.base import (
    ALIASES,
    architecture_name,
    get_bool,
    get_optional_int,
    get_required_int,
)
from kvscope.domain.model import ModelSpec
from kvscope.errors import ModelResolutionError
from kvscope.resolvers.base import RawModelConfig


def _spec(
    raw: RawModelConfig, architecture: str, *, allow_kv_fallback: bool = False
) -> ModelSpec:
    config = raw.raw_config
    layers = get_required_int(config, "num_hidden_layers", ALIASES["layers"])
    hidden = get_required_int(config, "hidden_size", ALIASES["hidden_size"])
    attention = get_required_int(
        config, "num_attention_heads", ALIASES["attention_heads"]
    )
    kv = get_optional_int(config, "num_key_value_heads", ALIASES["kv_heads"])
    if kv is None:
        if allow_kv_fallback:
            kv = attention
        else:
            raise ModelResolutionError(
                "num_key_value_heads is required; MHA fallback is not "
                "established for this architecture",
                code="missing_kv_heads",
                source=config,
            )
    explicit_head_dim = get_optional_int(
        config, "head_dim", ("head_dim", "attention_head_dim")
    )
    if explicit_head_dim is not None:
        head_dim = explicit_head_dim
    else:
        if hidden % attention:
            raise ModelResolutionError(
                "hidden_size must be divisible by num_attention_heads "
                "when head_dim is absent",
                code="non_divisible_attention_dimensions",
                source=config,
            )
        head_dim = hidden // attention
    if attention % kv:
        raise ModelResolutionError(
            "num_attention_heads must be divisible by num_key_value_heads",
            code="non_divisible_kv_heads",
            source=config,
        )
    if explicit_head_dim is not None and hidden != attention * head_dim:
        raise ModelResolutionError(
            "explicit head_dim is inconsistent with hidden_size and "
            "num_attention_heads",
            code="inconsistent_head_dim",
            source=config,
        )
    model_id = str(config.get("model_id", raw.model_id))
    return ModelSpec(
        model_id=model_id,
        architecture=architecture,
        num_hidden_layers=layers,
        hidden_size=hidden,
        num_attention_heads=attention,
        num_key_value_heads=kv,
        head_dim=head_dim,
        vocab_size=get_optional_int(config, "vocab_size", ("vocab_size",)),
        intermediate_size=get_optional_int(
            config, "intermediate_size", ALIASES["intermediate_size"]
        ),
        max_position_embeddings=get_optional_int(
            config, "max_position_embeddings", ALIASES["max_position_embeddings"]
        ),
        parameter_count=get_optional_int(
            config, "parameter_count", ("parameter_count", "num_parameters")
        ),
        active_parameter_count=get_optional_int(
            config, "active_parameter_count", ("active_parameter_count",)
        ),
        num_experts=get_optional_int(
            config, "num_experts", ("num_experts", "n_routed_experts")
        ),
        num_experts_per_tok=get_optional_int(
            config,
            "num_experts_per_tok",
            ("num_experts_per_tok", "num_selected_experts"),
        ),
        tie_word_embeddings=get_bool(config, "tie_word_embeddings"),
        source=raw.source_type,
    )


class LlamaAdapter:
    adapter_id = "llama"
    supported_model_types = frozenset({"llama", "mistral"})
    priority = 100

    def can_adapt(self, raw_config: Mapping[str, Any]) -> bool:
        return architecture_name(raw_config) in self.supported_model_types

    def adapt(self, raw: RawModelConfig) -> ModelSpec:
        return _spec(
            raw,
            "llama",
            allow_kv_fallback=architecture_name(raw.raw_config) in {"llama", "mistral"},
        )


class QwenAdapter:
    adapter_id = "qwen"
    supported_model_types = frozenset({"qwen", "qwen2", "qwen3", "qwen2_moe"})
    priority = 90

    def can_adapt(self, raw_config: Mapping[str, Any]) -> bool:
        name = architecture_name(raw_config)
        return name in self.supported_model_types or name.startswith("qwen")

    def adapt(self, raw: RawModelConfig) -> ModelSpec:
        return _spec(
            raw,
            "qwen",
            allow_kv_fallback=architecture_name(raw.raw_config)
            in {"qwen", "qwen2", "qwen3"},
        )


class DeepSeekAdapter:
    adapter_id = "deepseek"
    supported_model_types = frozenset(
        {"deepseek", "deepseek_v2", "deepseek_v3", "deepseek_moe"}
    )
    priority = 80

    def can_adapt(self, raw_config: Mapping[str, Any]) -> bool:
        name = architecture_name(raw_config)
        return name in self.supported_model_types or name.startswith("deepseek")

    def adapt(self, raw: RawModelConfig) -> ModelSpec:
        return _spec(raw, "deepseek", allow_kv_fallback=False)


class GenericDecoderAdapter:
    adapter_id = "generic_decoder"
    supported_model_types: frozenset[str] = frozenset()
    priority = 0

    def can_adapt(self, raw_config: Mapping[str, Any]) -> bool:
        return True

    def adapt(self, raw: RawModelConfig) -> ModelSpec:
        return _spec(raw, "generic_decoder", allow_kv_fallback=False)


ADAPTERS = (LlamaAdapter(), QwenAdapter(), DeepSeekAdapter())
