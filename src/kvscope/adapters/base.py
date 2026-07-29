"""Utilities shared by architecture adapters."""

from collections.abc import Mapping
from typing import Any

from kvscope.errors import ModelConfigConflictError, ModelResolutionError


def _values(raw: Mapping[str, Any], aliases: tuple[str, ...]) -> list[tuple[str, Any]]:
    return [
        (name, raw[name]) for name in aliases if name in raw and raw[name] is not None
    ]


def resolve_alias(
    raw: Mapping[str, Any], normalized_field: str, aliases: tuple[str, ...]
) -> tuple[Any, str | None, bool]:
    """Return a field value, rejecting conflicting aliases deterministically."""
    values = _values(raw, aliases)
    if not values:
        return None, None, False
    first_name, first = values[0]
    if any(value != first for _, value in values[1:]):
        raise ModelConfigConflictError(
            f"conflicting values for {normalized_field}: "
            + ", ".join(name for name, _ in values),
            code="model_config_conflict",
            source=raw,
            suggestion="Keep one alias or make all aliases equal.",
        )
    return first, first_name, first_name != aliases[0]


def get_required_int(
    raw: Mapping[str, Any], field: str, aliases: tuple[str, ...]
) -> int:
    value, source, _ = resolve_alias(raw, field, aliases)
    if value is None:
        raise ModelResolutionError(
            f"missing required model field '{field}'",
            code="missing_model_field",
            source=raw,
            suggestion=(
                "Provide the field in an explicit config or use a complete config.json."
            ),
        )
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelResolutionError(
            f"model field '{source or field}' must be a positive integer",
            code="invalid_model_field",
            source=raw,
        )
    return int(value)


def get_optional_int(
    raw: Mapping[str, Any], field: str, aliases: tuple[str, ...]
) -> int | None:
    value, source, _ = resolve_alias(raw, field, aliases)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelResolutionError(
            f"model field '{source or field}' must be a positive integer",
            code="invalid_model_field",
            source=raw,
        )
    return int(value)


def get_bool(raw: Mapping[str, Any], field: str) -> bool | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ModelResolutionError(
            f"model field '{field}' must be boolean", code="invalid_model_field"
        )
    return value


def architecture_name(raw: Mapping[str, Any]) -> str:
    model_type = raw.get("model_type")
    if isinstance(model_type, str):
        return model_type.lower()
    architectures = raw.get("architectures")
    if (
        isinstance(architectures, list)
        and architectures
        and isinstance(architectures[0], str)
    ):
        return architectures[0].lower()
    return ""


ALIASES: dict[str, tuple[str, ...]] = {
    "layers": ("num_hidden_layers", "n_layer", "num_layers"),
    "hidden_size": ("hidden_size", "n_embd", "d_model"),
    "attention_heads": ("num_attention_heads", "n_head", "num_heads"),
    "kv_heads": ("num_key_value_heads", "n_head_kv", "num_kv_heads"),
    "intermediate_size": ("intermediate_size", "n_inner", "ffn_hidden_size"),
    "max_position_embeddings": (
        "max_position_embeddings",
        "n_positions",
        "max_sequence_length",
        "seq_length",
    ),
}
