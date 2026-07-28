"""Inference configuration domain objects."""

from typing import Annotated

from pydantic import Field, StrictFloat, StrictInt

from kvscope.domain.base import DomainModel
from kvscope.domain.dtypes import KVDType, WeightDType

PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class InferenceConfig(DomainModel):
    """Validated workload and precision settings for an inference request."""

    weight_dtype: WeightDType
    kv_dtype: KVDType

    context_length: PositiveInt
    batch_size: PositiveInt = 1
    max_num_seqs: PositiveInt = 1

    prefix_tokens: NonNegativeInt = 0
    multimodal_tokens: NonNegativeInt = 0

    cpu_offload_bytes: NonNegativeInt = 0
    graph_capture_enabled: bool = True
    safety_margin_ratio: Annotated[StrictFloat, Field(ge=0, le=1)] = 0.05

    @property
    def active_sequences(self) -> int:
        """Return the v0.1 active-sequence interpretation for KV budgeting."""
        return max(self.batch_size, self.max_num_seqs)

    @property
    def active_sequences_source(self) -> str:
        """Trace whether batch_size or max_num_seqs determined active_sequences."""
        if self.batch_size > self.max_num_seqs:
            return "batch_size"
        if self.max_num_seqs > self.batch_size:
            return "max_num_seqs"
        return "equal"

