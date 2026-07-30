"""Model architecture domain objects."""

from typing import Annotated

from pydantic import Field, StrictInt, StrictStr, model_validator

from kvscope.domain.base import DomainModel

PositiveInt = Annotated[StrictInt, Field(gt=0)]


class ModelSpec(DomainModel):
    """Validated model metadata required by later memory calculations."""

    model_id: Annotated[StrictStr, Field(min_length=1)]
    architecture: Annotated[StrictStr, Field(min_length=1)]

    num_hidden_layers: PositiveInt
    hidden_size: PositiveInt
    num_attention_heads: PositiveInt
    num_key_value_heads: PositiveInt
    head_dim: PositiveInt

    vocab_size: PositiveInt | None = None
    intermediate_size: PositiveInt | None = None
    max_position_embeddings: PositiveInt | None = None

    parameter_count: PositiveInt | None = None
    active_parameter_count: PositiveInt | None = None

    num_experts: PositiveInt | None = None
    num_experts_per_tok: PositiveInt | None = None

    tie_word_embeddings: bool | None = None
    source: Annotated[StrictStr, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_model_spec(self) -> "ModelSpec":
        """Reject incompatible model architecture metadata without correcting it."""
        if self.num_key_value_heads > self.num_attention_heads:
            raise ValueError("num_key_value_heads must not exceed num_attention_heads")
        if self.num_attention_heads % self.num_key_value_heads != 0:
            raise ValueError(
                "num_attention_heads must be divisible by num_key_value_heads"
            )
        if (
            self.num_experts is not None
            and self.num_experts_per_tok is not None
            and self.num_experts_per_tok > self.num_experts
        ):
            raise ValueError("num_experts_per_tok must not exceed num_experts")
        if (
            self.parameter_count is not None
            and self.active_parameter_count is not None
            and self.active_parameter_count > self.parameter_count
        ):
            raise ValueError("active_parameter_count must not exceed parameter_count")
        return self
