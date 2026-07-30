"""Pure KV Cache sizing formulas and the KV Cache Engine entry point."""

from dataclasses import dataclass
from enum import StrEnum

from kvscope.domain.backend import BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.dtypes import KVDType
from kvscope.domain.enums import Confidence
from kvscope.domain.estimate import EstimateComponent
from kvscope.domain.model import ModelSpec
from kvscope.errors import InvalidModelConfigError, ProfileValidationError


class AttentionMode(StrEnum):
    """Attention layout represented by the query and KV head counts."""

    MHA = "mha"
    GQA = "gqa"
    MQA = "mqa"


@dataclass(frozen=True, slots=True)
class KVCacheFormulaInputs:
    """All values used by the KV Cache formula, expressed in base units.

    ``context_tokens`` is the requested text context. Prefix and multimodal
    tokens are explicit reservations added to it. ``block_size`` is a backend
    allocation unit; ``None`` means that no token-block alignment is applied.
    ``active_sequences_source`` traces whether batch_size or max_num_seqs
    determined the sequence count. ``prefix_shared`` indicates whether prefix
    tokens are shared across all active sequences in memory (e.g. RadixAttention).
    """

    num_hidden_layers: int
    num_attention_heads: int
    num_key_value_heads: int
    head_dim: int
    context_tokens: int
    prefix_tokens: int
    multimodal_tokens: int
    active_sequences: int
    kv_dtype: KVDType
    bytes_per_element: int
    block_size: int | None
    active_sequences_source: str = "equal"
    prefix_shared: bool = False

    @property
    def effective_tokens(self) -> int:
        """Return all tokens reserved per active sequence."""
        return self.context_tokens + self.prefix_tokens + self.multimodal_tokens

    @property
    def allocated_tokens(self) -> int:
        """Return effective tokens rounded up to the backend block size."""
        if self.block_size is None:
            return self.effective_tokens
        return (
            (self.effective_tokens + self.block_size - 1) // self.block_size
        ) * self.block_size

    @property
    def attention_mode(self) -> AttentionMode:
        """Return MHA, GQA, or MQA for the supplied head counts."""
        if self.num_key_value_heads == self.num_attention_heads:
            return AttentionMode.MHA
        if self.num_key_value_heads == 1:
            return AttentionMode.MQA
        return AttentionMode.GQA


@dataclass(frozen=True, slots=True)
class KVCacheEstimate:
    """Explainable KV Cache result with every byte value kept as an integer."""

    formula_inputs: KVCacheFormulaInputs
    raw_bytes: int
    allocated_bytes: int
    alignment_waste_bytes: int
    bytes_per_token: int
    bytes_per_sequence: int

    @property
    def effective_tokens(self) -> int:
        """Return the unaligned tokens reserved per active sequence."""
        return self.formula_inputs.effective_tokens

    @property
    def allocated_tokens(self) -> int:
        """Return the aligned tokens reserved per active sequence."""
        return self.formula_inputs.allocated_tokens

    @property
    def attention_mode(self) -> AttentionMode:
        """Return the attention layout used by the estimate."""
        return self.formula_inputs.attention_mode

    def to_estimate_component(self) -> EstimateComponent:
        """Convert the result to a domain EstimateComponent for reports."""
        formula_str = (
            "2 * layers * kv_heads * head_dim * bytes_per_elem * tokens * seqs"
        )
        return EstimateComponent(
            name="kv_cache",
            bytes=self.allocated_bytes,
            lower_bound_bytes=self.raw_bytes,
            upper_bound_bytes=self.allocated_bytes,
            confidence=Confidence.EXACT,
            formula=formula_str,
        )


def _validate_formula_inputs(inputs: KVCacheFormulaInputs) -> None:
    """Reject invalid formula operands before performing arithmetic."""
    if not isinstance(inputs.kv_dtype, KVDType):
        raise InvalidModelConfigError("kv_dtype must be a KVDType")

    positive_fields = (
        "num_hidden_layers",
        "num_attention_heads",
        "num_key_value_heads",
        "head_dim",
        "active_sequences",
        "bytes_per_element",
    )
    for field_name in positive_fields:
        value = getattr(inputs, field_name)
        if type(value) is not int or value <= 0:
            raise InvalidModelConfigError(f"{field_name} must be a positive integer")
    if inputs.bytes_per_element != inputs.kv_dtype.bytes_per_element:
        raise InvalidModelConfigError("bytes_per_element does not match kv_dtype")

    nonnegative_fields = (
        "context_tokens",
        "prefix_tokens",
        "multimodal_tokens",
    )
    for field_name in nonnegative_fields:
        value = getattr(inputs, field_name)
        if type(value) is not int or value < 0:
            raise InvalidModelConfigError(
                f"{field_name} must be a non-negative integer"
            )

    if inputs.effective_tokens <= 0:
        raise InvalidModelConfigError("at least one token must be reserved")
    if inputs.num_key_value_heads > inputs.num_attention_heads:
        raise InvalidModelConfigError(
            "num_key_value_heads must not exceed num_attention_heads"
        )
    if inputs.num_attention_heads % inputs.num_key_value_heads != 0:
        raise InvalidModelConfigError(
            "num_attention_heads must be divisible by num_key_value_heads"
        )
    if inputs.block_size is not None and (
        type(inputs.block_size) is not int or inputs.block_size <= 0
    ):
        raise InvalidModelConfigError("block_size must be a positive integer or None")


def calculate_kv_cache(inputs: KVCacheFormulaInputs) -> KVCacheEstimate:
    """Calculate raw and block-allocated KV bytes from formula inputs.

    The formula is intentionally pure: it only validates its immutable input
    value and performs integer arithmetic. ``bytes_per_token`` is the raw KV
    storage cost for one token in one active sequence, while
    ``bytes_per_sequence`` is the raw cost of one complete effective sequence.
    """
    _validate_formula_inputs(inputs)

    bytes_per_token = (
        2
        * inputs.num_hidden_layers
        * inputs.num_key_value_heads
        * inputs.head_dim
        * inputs.bytes_per_element
    )

    if inputs.prefix_shared:
        unshared_tokens = inputs.context_tokens + inputs.multimodal_tokens
        if inputs.block_size is None:
            unshared_allocated_tokens = unshared_tokens
            prefix_allocated_tokens = inputs.prefix_tokens
        else:
            bs = inputs.block_size
            unshared_allocated_tokens = (
                ((unshared_tokens + bs - 1) // bs) * bs if unshared_tokens > 0 else 0
            )
            prefix_allocated_tokens = (
                ((inputs.prefix_tokens + bs - 1) // bs) * bs
                if inputs.prefix_tokens > 0
                else 0
            )

        raw_bytes = bytes_per_token * (
            unshared_tokens * inputs.active_sequences + inputs.prefix_tokens
        )
        allocated_bytes = bytes_per_token * (
            unshared_allocated_tokens * inputs.active_sequences
            + prefix_allocated_tokens
        )
    else:
        raw_bytes = bytes_per_token * inputs.effective_tokens * inputs.active_sequences
        allocated_bytes = (
            bytes_per_token * inputs.allocated_tokens * inputs.active_sequences
        )

    return KVCacheEstimate(
        formula_inputs=inputs,
        raw_bytes=raw_bytes,
        allocated_bytes=allocated_bytes,
        alignment_waste_bytes=allocated_bytes - raw_bytes,
        bytes_per_token=bytes_per_token,
        bytes_per_sequence=bytes_per_token * inputs.effective_tokens,
    )


def estimate_kv_cache(
    model: ModelSpec,
    config: InferenceConfig,
    backend: BackendSpec,
) -> KVCacheEstimate:
    """Estimate KV Cache bytes for a model, workload, and backend profile."""
    if config.kv_dtype not in backend.supports_kv_dtypes:
        raise ProfileValidationError(
            f"backend {backend.backend_id!r} does not support KV dtype "
            f"{config.kv_dtype.value!r}"
        )

    return calculate_kv_cache(
        KVCacheFormulaInputs(
            num_hidden_layers=model.num_hidden_layers,
            num_attention_heads=model.num_attention_heads,
            num_key_value_heads=model.num_key_value_heads,
            head_dim=model.head_dim,
            context_tokens=config.context_length,
            prefix_tokens=config.prefix_tokens,
            multimodal_tokens=config.multimodal_tokens,
            active_sequences=config.active_sequences,
            kv_dtype=config.kv_dtype,
            bytes_per_element=config.kv_dtype.bytes_per_element,
            block_size=backend.kv_block_size,
            active_sequences_source=config.active_sequences_source,
        )
    )
